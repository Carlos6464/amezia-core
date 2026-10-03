import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type {
  AdminLoginRequest,
  ChangePasswordRequest,
  GoogleLoginRequest,
  LoginRequest,
  RegisterRequest,
  RequestPasswordResetRequest,
  ResetPasswordRequest,
  SetPasswordRequest,
  UpdateOnboardingRequest,
  UpdateProfileRequest,
  User,
} from '@amezia/shared-types';
import { Observable, map, tap } from 'rxjs';

import { LanguageService } from '../i18n/language.service';
import { WebSocketService } from '../websocket/websocket.service';
import { AuthApiService } from '../../features/auth/data-access/auth-api.service';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Estado de sessão do usuário via Signals (currentUser,
 * accessToken em memória — nunca localStorage, RN-08) e orquestração dos
 * fluxos de auth sobre o AuthApiService. Sincroniza `language` com o
 * LanguageService (Transloco) e liga/desliga o WebSocket conforme a sessão.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly authApi = inject(AuthApiService);
  private readonly languageService = inject(LanguageService);
  private readonly webSocketService = inject(WebSocketService);
  private readonly router = inject(Router);

  private readonly _currentUser = signal<User | null>(null);
  private readonly _accessToken = signal<string | null>(null);

  readonly currentUser = this._currentUser.asReadonly();
  readonly accessToken = this._accessToken.asReadonly();
  readonly isAuthenticated = computed(() => this._accessToken() !== null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Cria a conta local e já aplica a sessão retornada
   * (registro = login automático).
   */
  register(payload: RegisterRequest): Observable<User> {
    return this.authApi
      .register(payload)
      .pipe(map((res) => this._applySession(res.user, res.access_token)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Autentica por email/senha e aplica a sessão (Signals +
   * WebSocket + idioma).
   */
  login(payload: LoginRequest): Observable<User> {
    return this.authApi
      .login(payload)
      .pipe(map((res) => this._applySession(res.user, res.access_token)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Autentica via id_token do Google (botão GoogleAuthButton)
   * e aplica a sessão retornada.
   */
  loginWithGoogle(payload: GoogleLoginRequest): Observable<User> {
    return this.authApi
      .loginWithGoogle(payload)
      .pipe(map((res) => this._applySession(res.user, res.access_token)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Autentica na porta de entrada própria do Painel Admin
   * (`/api/v1/admin/auth/login`) — mesma sessão única do resto do
   * sistema (RN-08, `_applySession` idêntico ao `login()` comum), só a
   * checagem de `role=admin` acontece no backend antes de emitir os
   * tokens. Painel cliente e painel admin são telas isoladas, mas
   * continuam usando o mesmo AuthService/sessão por trás — decisão de
   * produto de 2026-08-15.
   */
  loginAdmin(payload: AdminLoginRequest): Observable<User> {
    return this.authApi
      .adminLogin(payload)
      .pipe(map((res) => this._applySession(res.user, res.access_token)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Completa o login via redirect OAuth2 do Google
   * (`GoogleCallbackPage`, `GET /auth/google/callback` já emitiu o access
   * token na query string e setou o cookie HttpOnly de refresh). Diferente
   * de `_applySession`, aqui só se tem o token — busca o perfil via
   * `getMe()` antes de aplicar a sessão.
   */
  completeGoogleRedirect(accessToken: string): Observable<User> {
    this._accessToken.set(accessToken);
    return this.authApi.getMe().pipe(
      tap((user) => {
        this._setUser(user);
        this.webSocketService.connect(accessToken);
      }),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Renovação silenciosa do access token via cookie HttpOnly de
   * refresh (enviado automaticamente pelo browser). Usado pelo
   * jwtInterceptor em resposta a 401.
   */
  refreshAccessToken(): Observable<string> {
    return this.authApi.refresh().pipe(
      tap((res) => this._accessToken.set(res.access_token)),
      map((res) => res.access_token),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Busca o perfil do usuário autenticado e atualiza o Signal
   * `currentUser` — usado no bootstrap (provideAppInitializer) para
   * restaurar a sessão após um reload de página.
   */
  loadCurrentUser(): Observable<User> {
    return this.authApi.getMe().pipe(tap((user) => this._setUser(user)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Atualiza campos parciais do perfil e sincroniza o
   * `currentUser` local (inclusive troca de idioma em runtime via
   * LanguageService).
   */
  updateProfile(payload: UpdateProfileRequest): Observable<User> {
    return this.authApi.updateProfile(payload).pipe(tap((user) => this._setUser(user)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Marca/desmarca o onboarding guiado e sincroniza o
   * `currentUser` local — usado pelo `OnboardingService`.
   */
  updateOnboarding(payload: UpdateOnboardingRequest): Observable<User> {
    return this.authApi.updateOnboarding(payload).pipe(tap((user) => this._setUser(user)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Troca a senha do usuário autenticado (exige a senha
   * atual) — sem efeito colateral sobre a sessão.
   */
  changePassword(payload: ChangePasswordRequest): Observable<{ detail: string }> {
    return this.authApi.changePassword(payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Define a senha local pela primeira vez (conta só-OAuth,
   * `has_password=false`) e sincroniza `currentUser` com o retorno
   * (`has_password=true`), sem precisar de um reload/`getMe()` extra.
   */
  setPassword(payload: SetPasswordRequest): Observable<User> {
    return this.authApi.setPassword(payload).pipe(tap((user) => this._setUser(user)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Dispara o email de reset de senha — sempre resolve com
   * sucesso, não revela se o email existe.
   */
  requestPasswordReset(payload: RequestPasswordResetRequest): Observable<{ detail: string }> {
    return this.authApi.requestPasswordReset(payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Confirma o reset de senha a partir do token recebido por
   * email.
   */
  resetPassword(payload: ResetPasswordRequest): Observable<{ detail: string }> {
    return this.authApi.resetPassword(payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Limpa a sessão e navega para `redirectTo` (padrão
   * `/login`) — os guards só rodam em eventos de navegação, então sem
   * esse redirect explícito o usuário ficaria "logado visualmente" na
   * rota protegida atual até navegar de novo por conta própria.
   * `redirectTo` existe desde 2026-08-15 (build-context-06) pro logout
   * do Painel Admin voltar pra `/admin/login`, nunca pra `/login` — os
   * dois painéis são isolados, o logout de um não deveria "vazar" pro
   * login do outro.
   */
  logout(redirectTo = '/login'): void {
    this.authApi.logout().subscribe({
      next: () => this._logoutLocally(redirectTo),
      error: () => this._logoutLocally(redirectTo),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Limpa a sessão e navega para `redirectTo` — chamado tanto
   * no sucesso quanto na falha do logout remoto (o resultado local é o
   * mesmo em ambos os casos).
   */
  private _logoutLocally(redirectTo: string): void {
    this.clearSession();
    this.router.navigateByUrl(redirectTo);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Exclui a conta e limpa a sessão local em seguida — quem
   * chama (profile-page) é responsável por navegar para /login depois.
   */
  deleteAccount(): Observable<void> {
    return this.authApi.deleteAccount().pipe(tap(() => this.clearSession()));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Limpa a sessão local sem chamar o backend — usado pelo
   * jwtInterceptor quando o refresh silencioso falha (refresh token
   * expirado/inválido/ausente).
   */
  clearSession(): void {
    this._currentUser.set(null);
    this._accessToken.set(null);
    this.webSocketService.disconnect();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Aplica uma sessão nova (register/login/loginWithGoogle) —
   * guarda o access token, sincroniza o usuário e conecta o WebSocket.
   */
  private _applySession(user: User, accessToken: string): User {
    this._accessToken.set(accessToken);
    this._setUser(user);
    this.webSocketService.connect(accessToken);
    return user;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Atualiza o Signal `currentUser` e sincroniza o idioma
   * ativo do Transloco com a preferência salva no perfil (RN-10).
   */
  private _setUser(user: User): void {
    this._currentUser.set(user);
    this.languageService.setLanguage(user.language);
  }
}
