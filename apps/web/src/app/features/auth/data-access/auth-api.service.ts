import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type {
  AdminLoginRequest,
  AuthTokensResponse,
  ChangePasswordRequest,
  GoogleLoginRequest,
  LoginRequest,
  RefreshResponse,
  RegisterRequest,
  RequestPasswordResetRequest,
  ResetPasswordRequest,
  SetPasswordRequest,
  UpdateOnboardingRequest,
  UpdateProfileRequest,
  User,
} from '@amezia/shared-types';
import { Observable } from 'rxjs';

const BASE_URL = '/api/v1/auth';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Chamadas HTTP cruas aos 11 endpoints de /api/v1/auth — sem
 * estado, sem Signals. O AuthService (core/auth) orquestra essas chamadas
 * e mantém o estado de sessão.
 */
@Injectable({ providedIn: 'root' })
export class AuthApiService {
  private readonly http = inject(HttpClient);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: POST /auth/register.
   */
  register(payload: RegisterRequest): Observable<AuthTokensResponse> {
    return this.http.post<AuthTokensResponse>(`${BASE_URL}/register`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: POST /auth/login.
   */
  login(payload: LoginRequest): Observable<AuthTokensResponse> {
    return this.http.post<AuthTokensResponse>(`${BASE_URL}/login`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: POST /auth/login/google.
   */
  loginWithGoogle(payload: GoogleLoginRequest): Observable<AuthTokensResponse> {
    return this.http.post<AuthTokensResponse>(`${BASE_URL}/login/google`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: POST /admin/auth/login — porta de entrada isolada do
   * Painel Admin (build-context-06). Mesmo formato de resposta do login
   * comum; o backend rejeita contas sem `role=admin` com a mesma
   * resposta de credenciais inválidas.
   */
  adminLogin(payload: AdminLoginRequest): Observable<AuthTokensResponse> {
    return this.http.post<AuthTokensResponse>('/api/v1/admin/auth/login', payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: POST /auth/refresh — o cookie HttpOnly de refresh vai
   * junto automaticamente (same-origin), não precisa ser lido/anexado
   * manualmente aqui.
   */
  refresh(): Observable<RefreshResponse> {
    return this.http.post<RefreshResponse>(`${BASE_URL}/refresh`, {});
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: POST /auth/logout.
   */
  logout(): Observable<void> {
    return this.http.post<void>(`${BASE_URL}/logout`, {});
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: POST /auth/password-reset/request.
   */
  requestPasswordReset(payload: RequestPasswordResetRequest): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${BASE_URL}/password-reset/request`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: POST /auth/password-reset/confirm.
   */
  resetPassword(payload: ResetPasswordRequest): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${BASE_URL}/password-reset/confirm`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: GET /auth/me.
   */
  getMe(): Observable<User> {
    return this.http.get<User>(`${BASE_URL}/me`);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: PATCH /auth/me.
   */
  updateProfile(payload: UpdateProfileRequest): Observable<User> {
    return this.http.patch<User>(`${BASE_URL}/me`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: PATCH /auth/me/onboarding.
   */
  updateOnboarding(payload: UpdateOnboardingRequest): Observable<User> {
    return this.http.patch<User>(`${BASE_URL}/me/onboarding`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: PATCH /auth/me/password.
   */
  changePassword(payload: ChangePasswordRequest): Observable<{ detail: string }> {
    return this.http.patch<{ detail: string }>(`${BASE_URL}/me/password`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: POST /auth/me/password — define a senha local pela
   * primeira vez (conta só-OAuth, `has_password=false`). Devolve o
   * usuário atualizado (`has_password=true`), diferente de
   * `changePassword` (que só devolve um detail).
   */
  setPassword(payload: SetPasswordRequest): Observable<User> {
    return this.http.post<User>(`${BASE_URL}/me/password`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: DELETE /auth/me.
   */
  deleteAccount(): Observable<void> {
    return this.http.delete<void>(`${BASE_URL}/me`);
  }
}
