import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { AuthService } from '../../../../core/auth/auth.service';
import { ThemeService } from '../../../../core/theme/theme.service';
import { AdminBrandPanelComponent } from '../../../admin/ui/admin-brand-panel/admin-brand-panel.component';
import { AuthBrandPanelComponent } from '../../ui/auth-brand-panel/auth-brand-panel.component';
import { AuthMobileBrandComponent } from '../../ui/auth-mobile-brand/auth-mobile-brand.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Tela "Esqueci minha senha" (/forgot-password) — sem
 * protótipo próprio (build-context-01 §3.2.3). Mensagem de confirmação é
 * sempre genérica, não revela se o email existe. Desde 2026-08-15,
 * também é o destino do link "Esqueceu a senha?" do `/admin/login` — é
 * a mesma senha, mesma conta, nos dois painéis (não existe um fluxo de
 * reset "admin" separado), mas a tela adapta a cor conforme a origem
 * (`?from=admin`), senão fica com a cor do painel cliente mesmo vinda
 * do admin, o que ficava visualmente inconsistente.
 */
@Component({
  selector: 'app-forgot-password-page',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoModule,
    AuthBrandPanelComponent,
    AuthMobileBrandComponent,
    AdminBrandPanelComponent,
  ],
  templateUrl: './forgot-password-page.component.html',
  styleUrl: './forgot-password-page.component.css',
})
export class ForgotPasswordPageComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  protected readonly themeService = inject(ThemeService);

  readonly submitting = signal(false);
  readonly submitted = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: `true` quando a tela foi aberta a partir do `/admin/login`
   * (`?from=admin`) — controla qual painel de marca renderiza, o tema
   * preto e pra onde o link "Voltar ao login" aponta.
   */
  protected readonly isFromAdmin = signal(false);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Lê a origem da query string e liga o tema preto
   * (`data-panel="admin"`) quando aplicável — mesmo mecanismo do
   * `AdminLoginPageComponent`.
   */
  ngOnInit(): void {
    const fromAdmin = this.route.snapshot.queryParamMap.get('from') === 'admin';
    this.isFromAdmin.set(fromAdmin);
    if (fromAdmin) {
      document.documentElement.dataset['panel'] = 'admin';
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Remove o tema preto ao sair da tela, se tinha sido
   * ligado — sem isso, navegar pro painel cliente em seguida manteria
   * a paleta preta indevidamente.
   */
  ngOnDestroy(): void {
    if (this.isFromAdmin()) {
      delete document.documentElement.dataset['panel'];
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Dispara o pedido de reset e sempre mostra a mesma
   * confirmação genérica, tanto no sucesso quanto no erro — a API já
   * responde 200 em ambos os casos (anti-enumeração de email), mas o
   * `error` aqui cobre falhas de rede/infra também.
   */
  submit(): void {
    if (this.form.invalid || this.submitting()) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.authService.requestPasswordReset(this.form.getRawValue()).subscribe({
      next: () => {
        this.submitting.set(false);
        this.submitted.set(true);
      },
      error: () => {
        this.submitting.set(false);
        this.submitted.set(true);
      },
    });
  }
}
