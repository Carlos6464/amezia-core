import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { AuthService } from '../../../../core/auth/auth.service';
import { ThemeService } from '../../../../core/theme/theme.service';
import { AuthBrandPanelComponent } from '../../ui/auth-brand-panel/auth-brand-panel.component';
import { AuthMobileBrandComponent } from '../../ui/auth-mobile-brand/auth-mobile-brand.component';
import { GoogleAuthButtonComponent } from '../../ui/google-auth-button/google-auth-button.component';
import { PasswordFieldComponent } from '../../ui/password-field/password-field.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Tela de login (/login) — layout split (painel de marca +
 * formulário) a partir de referência visual fornecida pelo usuário.
 */
@Component({
  selector: 'app-login-page',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoModule,
    AuthBrandPanelComponent,
    AuthMobileBrandComponent,
    GoogleAuthButtonComponent,
    PasswordFieldComponent,
  ],
  templateUrl: './login-page.component.html',
  styleUrl: './login-page.component.css',
})
export class LoginPageComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  protected readonly themeService = inject(ThemeService);

  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Valida o formulário, chama LoginUseCase (via AuthService)
   * e redireciona em caso de sucesso; mostra erro genérico (não revela
   * qual dado está errado) em caso de falha.
   */
  submit(): void {
    if (this.form.invalid || this.submitting()) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    this.authService.login(this.form.getRawValue()).subscribe({
      next: () => this.redirectAfterLogin(),
      error: () => {
        this.submitting.set(false);
        this.errorMessage.set('auth.login.invalidCredentials');
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Volta para a rota original que o authGuard preservou em
   * `returnUrl` (ex.: usuário tentou acessar /settings/profile sem
   * sessão), ou /dashboard por padrão.
   */
  private redirectAfterLogin(): void {
    const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') ?? '/dashboard';
    this.router.navigateByUrl(returnUrl);
  }
}
