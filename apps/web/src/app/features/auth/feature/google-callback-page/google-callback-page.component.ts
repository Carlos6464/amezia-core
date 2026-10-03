import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { AuthService } from '../../../../core/auth/auth.service';
import { ThemeService } from '../../../../core/theme/theme.service';
import { AuthBrandPanelComponent } from '../../ui/auth-brand-panel/auth-brand-panel.component';
import { AuthMobileBrandComponent } from '../../ui/auth-mobile-brand/auth-mobile-brand.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Página de transição do fluxo de login via redirect OAuth2 do
 * Google (`/google-callback?token=...` ou `?error=...`, gerada pelo
 * backend em `GET /auth/google/callback`). Sem ação própria do usuário —
 * só consome o resultado e navega. Rota sem guard: nem authGuard nem
 * publicOnlyGuard fazem sentido aqui, o usuário está literalmente no meio
 * da transição entre os dois estados de sessão.
 */
@Component({
  selector: 'app-google-callback-page',
  standalone: true,
  imports: [RouterLink, TranslocoModule, AuthBrandPanelComponent, AuthMobileBrandComponent],
  templateUrl: './google-callback-page.component.html',
  styleUrl: './google-callback-page.component.css',
})
export class GoogleCallbackPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly authService = inject(AuthService);
  protected readonly themeService = inject(ThemeService);

  readonly failed = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Lê `token` da query string. Se presente, completa a sessão
   * (`AuthService.completeGoogleRedirect`, que busca o perfil e liga o
   * WebSocket) e navega para /dashboard; se ausente (ou a busca do perfil
   * falhar), mostra o estado de erro com um link de volta pro /login. O
   * backend já usa `?error=google_auth_failed` nesse caso, mas a página
   * não distingue os motivos — qualquer ausência de token é tratada como
   * falha, a mesma mensagem cobre os dois.
   */
  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');

    if (!token) {
      this.failed.set(true);
      return;
    }

    this.authService.completeGoogleRedirect(token).subscribe({
      next: () => this.router.navigateByUrl('/dashboard'),
      error: () => this.failed.set(true),
    });
  }
}
