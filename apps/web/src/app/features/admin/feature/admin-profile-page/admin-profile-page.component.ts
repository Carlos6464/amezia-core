import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Component, computed, inject, signal } from '@angular/core';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { MessageService } from 'primeng/api';

import { AuthService } from '../../../../core/auth/auth.service';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Gera as iniciais do avatar (primeiro + último nome) — mesma
 * função de `ProfilePageComponent` (painel cliente), duplicada aqui
 * porque o Painel Admin não importa nada do painel cliente.
 */
function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Validator de grupo — compara `newPassword`/`confirmPassword`,
 * mesma função de `ProfilePageComponent`.
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
 * Data: 2026-08-15
 * Descrição: Tela de Perfil do Admin (`/admin/profile`) — pedido do
 * usuário depois de ver que o painel só tinha um dropdown com nome/
 * email/sair, sem uma área de verdade. É a **mesma conta/sessão** do
 * painel cliente (RN-08), então reaproveita os mesmos endpoints
 * (`AuthService.updateProfile`/`changePassword`/`setPassword`) — só a
 * UI é própria do admin (preto, `admin-design.css`-like), duplicada de
 * `ProfilePageComponent` (painéis isolados, sem import cruzado).
 * Escopo menor que o perfil do cliente, de propósito: sem preferência
 * de idioma nem exclusão de conta (ambos já cobertos por
 * `/settings/profile`, redundante duplicar aqui).
 */
@Component({
  selector: 'app-admin-profile-page',
  standalone: true,
  imports: [ReactiveFormsModule, TranslocoModule],
  templateUrl: './admin-profile-page.component.html',
  styleUrl: './admin-profile-page.component.css',
})
export class AdminProfilePageComponent {
  private readonly fb = inject(FormBuilder);
  protected readonly authService = inject(AuthService);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);

  protected readonly user = this.authService.currentUser;
  protected readonly initials = computed(() => initialsOf(this.user()?.name ?? ''));
  protected readonly isGoogleAccount = computed(() => this.user()?.oauth_provider === 'google');
  protected readonly hasPassword = computed(() => this.user()?.has_password ?? true);

  protected readonly personalInfoForm = this.fb.nonNullable.group({
    name: [this.user()?.name ?? '', [Validators.required, Validators.minLength(1)]],
    phone: [this.user()?.phone ?? ''],
  });

  protected readonly passwordForm = this.fb.nonNullable.group(
    {
      currentPassword: ['', Validators.required],
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required],
    },
    { validators: passwordsMatchValidator },
  );

  protected readonly setPasswordForm = this.fb.nonNullable.group(
    {
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required],
    },
    { validators: passwordsMatchValidator },
  );

  readonly savingPersonalInfo = signal(false);
  readonly personalInfoSaved = signal(false);

  readonly savingPassword = signal(false);
  readonly passwordError = signal<string | null>(null);
  readonly passwordSaved = signal(false);

  readonly savingSetPassword = signal(false);
  readonly setPasswordError = signal<string | null>(null);
  readonly setPasswordSaved = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Salva nome/telefone via UpdateProfileUseCase (mesmo
   * endpoint do painel cliente). Sucesso já tem o banner inline
   * `personalInfoSaved`; erro ganhou toast (build-context-13) — antes
   * ficava mudo, mesmo caso do painel cliente.
   */
  savePersonalInfo(): void {
    if (this.personalInfoForm.invalid || this.savingPersonalInfo()) {
      this.personalInfoForm.markAllAsTouched();
      return;
    }

    this.savingPersonalInfo.set(true);
    this.personalInfoSaved.set(false);
    this.authService.updateProfile(this.personalInfoForm.getRawValue()).subscribe({
      next: () => {
        this.savingPersonalInfo.set(false);
        this.personalInfoSaved.set(true);
      },
      error: () => {
        this.savingPersonalInfo.set(false);
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('toasts.errorTitle'),
          detail: this.transloco.translate('toasts.profile.saveError'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Troca a senha (exige a atual) — só aparece quando a
   * conta já tem uma senha local (`hasPassword()`).
   */
  changePassword(): void {
    if (this.passwordForm.invalid || this.savingPassword()) {
      this.passwordForm.markAllAsTouched();
      return;
    }

    this.savingPassword.set(true);
    this.passwordError.set(null);
    this.passwordSaved.set(false);

    const { currentPassword, newPassword } = this.passwordForm.getRawValue();
    this.authService
      .changePassword({ current_password: currentPassword, new_password: newPassword })
      .subscribe({
        next: () => {
          this.savingPassword.set(false);
          this.passwordSaved.set(true);
          this.passwordForm.reset({ currentPassword: '', newPassword: '', confirmPassword: '' });
        },
        error: () => {
          this.savingPassword.set(false);
          this.passwordError.set('admin.profile.security.changePasswordError');
        },
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Define a senha local pela primeira vez — só aparece
   * quando a conta ainda não tem uma (`!hasPassword()`, tipicamente uma
   * conta só-OAuth).
   */
  setPassword(): void {
    if (this.setPasswordForm.invalid || this.savingSetPassword()) {
      this.setPasswordForm.markAllAsTouched();
      return;
    }

    this.savingSetPassword.set(true);
    this.setPasswordError.set(null);
    this.setPasswordSaved.set(false);

    const { newPassword } = this.setPasswordForm.getRawValue();
    this.authService.setPassword({ new_password: newPassword }).subscribe({
      next: () => {
        this.savingSetPassword.set(false);
        this.setPasswordSaved.set(true);
        this.setPasswordForm.reset({ newPassword: '', confirmPassword: '' });
      },
      error: () => {
        this.savingSetPassword.set(false);
        this.setPasswordError.set('admin.profile.security.setPasswordError');
      },
    });
  }
}
