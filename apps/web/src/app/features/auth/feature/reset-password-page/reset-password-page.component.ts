import { Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { AuthService } from '../../../../core/auth/auth.service';
import { ThemeService } from '../../../../core/theme/theme.service';
import { AuthBrandPanelComponent } from '../../ui/auth-brand-panel/auth-brand-panel.component';
import { AuthMobileBrandComponent } from '../../ui/auth-mobile-brand/auth-mobile-brand.component';
import { PasswordFieldComponent } from '../../ui/password-field/password-field.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Validator de grupo — compara `newPassword`/`confirmPassword`
 * e marca `passwordsMismatch` quando divergem.
 */
function passwordsMatchValidator(control: AbstractControl): ValidationErrors | null {
  const password = control.get('newPassword')?.value;
  const confirmPassword = control.get('confirmPassword')?.value;
  return password && confirmPassword && password !== confirmPassword
    ? { passwordsMismatch: true }
    : null;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Tela de redefinição de senha (/reset-password?token=...) —
 * sem protótipo próprio (build-context-01 §3.2.3). Token lido da query
 * string e enviado junto com a nova senha ao ResetPasswordUseCase.
 */
@Component({
  selector: 'app-reset-password-page',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoModule,
    AuthBrandPanelComponent,
    AuthMobileBrandComponent,
    PasswordFieldComponent,
  ],
  templateUrl: './reset-password-page.component.html',
  styleUrl: './reset-password-page.component.css',
})
export class ResetPasswordPageComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  protected readonly themeService = inject(ThemeService);

  private readonly token = this.route.snapshot.queryParamMap.get('token') ?? '';

  readonly submitting = signal(false);
  readonly submitted = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group(
    {
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required],
    },
    { validators: passwordsMatchValidator },
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Envia o token (lido da query string no construtor) junto
   * com a nova senha ao ResetPasswordUseCase. Bloqueia o submit
   * localmente se o token estiver ausente, sem nem chamar a API.
   */
  submit(): void {
    if (this.form.invalid || this.submitting() || !this.token) {
      this.form.markAllAsTouched();
      if (!this.token) {
        this.errorMessage.set('auth.resetPassword.missingToken');
      }
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    this.authService
      .resetPassword({ token: this.token, new_password: this.form.getRawValue().newPassword })
      .subscribe({
        next: () => {
          this.submitting.set(false);
          this.submitted.set(true);
        },
        error: () => {
          this.submitting.set(false);
          this.errorMessage.set('auth.resetPassword.invalidOrExpired');
        },
      });
  }
}
