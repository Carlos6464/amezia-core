import { Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import type { BillingCycle, PaidPlan } from '@amezia/shared-types';

import { AuthService } from '../../../../core/auth/auth.service';
import { ThemeService } from '../../../../core/theme/theme.service';
import { SubscriptionService } from '../../../subscription/data-access/subscription.service';
import { AuthBrandPanelComponent } from '../../ui/auth-brand-panel/auth-brand-panel.component';
import { AuthMobileBrandComponent } from '../../ui/auth-mobile-brand/auth-mobile-brand.component';
import { GoogleAuthButtonComponent } from '../../ui/google-auth-button/google-auth-button.component';
import { PasswordFieldComponent } from '../../ui/password-field/password-field.component';

const PAID_PLANS: readonly string[] = ['pro', 'premium'];

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Validator de grupo — compara `password`/`confirmPassword` e
 * marca `passwordsMismatch` quando divergem. Client-side only: o backend
 * nunca recebe `confirmPassword`.
 */
function passwordsMatchValidator(control: AbstractControl): ValidationErrors | null {
  const password = control.get('password')?.value;
  const confirmPassword = control.get('confirmPassword')?.value;
  return password && confirmPassword && password !== confirmPassword
    ? { passwordsMismatch: true }
    : null;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Tela de registro (/register) a partir de screem/register-form.
 * Confirmação de senha é validação client-side only; só `password` é
 * enviado ao backend. Desde 2026-09-10 (build-context-09), passo 2/3 do
 * fluxo — se chegar com `?plan=pro|premium&billing=monthly|annual` (vindo
 * de `register-plan-page`), dispara o checkout do Stripe logo após o
 * cadastro em vez de ir direto pro dashboard; sem esses parâmetros, o
 * comportamento é o mesmo de sempre (cadastro Free, direto pro dashboard).
 */
@Component({
  selector: 'app-register-page',
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
  templateUrl: './register-page.component.html',
  styleUrl: './register-page.component.css',
})
export class RegisterPageComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly subscriptionService = inject(SubscriptionService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  protected readonly themeService = inject(ThemeService);

  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  protected readonly selectedPlan: PaidPlan | null;
  protected readonly selectedBillingCycle: BillingCycle;

  readonly form = this.fb.nonNullable.group(
    {
      name: ['', [Validators.required, Validators.minLength(1)]],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required],
      acceptTerms: [false, Validators.requiredTrue],
    },
    { validators: passwordsMatchValidator },
  );

  constructor() {
    const planParam = this.route.snapshot.queryParamMap.get('plan');
    this.selectedPlan = PAID_PLANS.includes(planParam ?? '') ? (planParam as PaidPlan) : null;
    this.selectedBillingCycle =
      this.route.snapshot.queryParamMap.get('billing') === 'annual' ? 'annual' : 'monthly';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Valida o formulário, envia só name/email/password (nunca
   * confirmPassword) ao RegisterUserUseCase e aplica o pós-cadastro
   * (`afterRegisterSuccess`) — registro já autentica. Distingue erro de
   * email duplicado (409) do erro genérico para a mensagem certa.
   */
  submit(): void {
    if (this.form.invalid || this.submitting()) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    const { name, email, password } = this.form.getRawValue();
    this.authService.register({ name, email, password }).subscribe({
      next: () => this.afterRegisterSuccess(),
      error: (err) => {
        this.submitting.set(false);
        this.errorMessage.set(
          err.status === 409 ? 'auth.register.emailTaken' : 'auth.register.genericError',
        );
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Sem plano pago selecionado (cadastro Free, fluxo antigo),
   * vai direto pro dashboard. Com plano pago, dispara `POST
   * /subscriptions/checkout` e redireciona pro Stripe (`checkout_url`) —
   * a conta Free já foi criada de qualquer forma (`RegisterUserUseCase`
   * nunca pula isso), então uma falha aqui não perde o cadastro: só cai
   * de volta pro dashboard, sem o plano pago aplicado ainda.
   */
  private afterRegisterSuccess(): void {
    if (this.selectedPlan === null) {
      this.router.navigateByUrl('/dashboard');
      return;
    }

    this.subscriptionService
      .checkout({ plan: this.selectedPlan, billing_cycle: this.selectedBillingCycle })
      .subscribe({
        next: (result) => {
          if (result.checkout_url) {
            window.location.href = result.checkout_url;
            return;
          }
          this.router.navigateByUrl('/dashboard');
        },
        error: () => this.router.navigateByUrl('/dashboard'),
      });
  }
}
