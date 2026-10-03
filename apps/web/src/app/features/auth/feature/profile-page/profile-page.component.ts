import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, effect, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  FormsModule,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Router } from '@angular/router';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { MessageService } from 'primeng/api';

import { AuthService } from '../../../../core/auth/auth.service';
import { BotInfoService } from '../../../../layout/onboarding/bot-info.service';
import { OnboardingService } from '../../../../layout/onboarding/onboarding.service';
import { BudgetService } from '../../../transactions/data-access/budget.service';
import {
  formatPhoneDigits,
  normalizePhoneForSubmit,
  phoneCompleteValidator,
} from '../../../../shared/utils/phone-mask';
import { DeleteAccountPanelComponent } from '../../ui/delete-account-panel/delete-account-panel.component';
import { PasswordFieldComponent } from '../../ui/password-field/password-field.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Gera as iniciais do avatar (primeiro + último nome) a partir
 * do nome completo — sem upload de foto, RN do build-context-01 §3.2.4.
 */
function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Validator de grupo — compara `newPassword`/`confirmPassword`
 * do formulário de troca de senha.
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
 * Descrição: Tela de Perfil (/settings/profile) a partir de
 * screem/settings-profile — só a aba Perfil existe neste build-context
 * (build-context-01 §3.2.4). Avatar de iniciais sem upload, sem badge de
 * plano/fuso horário/toggles de notificação (fora de escopo do MVP1).
 */
@Component({
  selector: 'app-profile-page',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    FormsModule,
    TranslocoModule,
    DatePipe,
    PasswordFieldComponent,
    DeleteAccountPanelComponent,
  ],
  templateUrl: './profile-page.component.html',
  styleUrl: './profile-page.component.css',
})
export class ProfilePageComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  protected readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly onboarding = inject(OnboardingService);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);
  protected readonly botInfoService = inject(BotInfoService);
  protected readonly budgetService = inject(BudgetService);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Carrega o número do bot pro card "Bot WhatsApp" e o teto
   * mensal (2026-08-18, novo campo editável nesta tela) assim que a
   * tela abre.
   */
  ngOnInit(): void {
    this.botInfoService.load();
    this.budgetService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Clique no botão "Salvar contato" (link `wa.me/...`) —
   * marca o item "bot_number" do checklist de onboarding. Não dá pra
   * confirmar que o usuário de fato salvou o contato (a página abre o
   * WhatsApp externamente), então isso é otimista, mesmo espírito do
   * item "google" no projeto irmão (também não verificável de verdade).
   */
  protected onBotContactClicked(): void {
    this.onboarding.markDone('bot_number');
  }

  protected readonly user = this.authService.currentUser;
  protected readonly initials = computed(() => initialsOf(this.user()?.name ?? ''));
  protected readonly isGoogleAccount = computed(() => this.user()?.oauth_provider === 'google');
  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Independente de `isGoogleAccount()` — uma conta vinculada
   * ao Google pode ou não ter uma senha local também (account linking).
   * Decide qual dos dois formulários (definir vs. trocar) aparece.
   */
  protected readonly hasPassword = computed(() => this.user()?.has_password ?? true);

  protected readonly personalInfoForm = this.fb.nonNullable.group({
    name: [this.user()?.name ?? '', [Validators.required, Validators.minLength(1)]],
    phone: [
      formatPhoneDigits((this.user()?.phone ?? '').replace(/\D/g, '')),
      [phoneCompleteValidator],
    ],
  });

  protected readonly passwordForm = this.fb.nonNullable.group(
    {
      currentPassword: ['', Validators.required],
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required],
    },
    { validators: passwordsMatchValidator },
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Formulário de "definir senha" (conta só-OAuth,
   * `has_password=false`) — sem campo de senha atual, diferente de
   * `passwordForm` (troca).
   */
  protected readonly setPasswordForm = this.fb.nonNullable.group(
    {
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required],
    },
    { validators: passwordsMatchValidator },
  );

  protected readonly preferencesForm = this.fb.nonNullable.group({
    language: [this.user()?.language ?? 'pt-BR'],
  });

  readonly savingPersonalInfo = signal(false);
  readonly personalInfoSaved = signal(false);

  readonly savingPassword = signal(false);
  readonly passwordError = signal<string | null>(null);
  readonly passwordSaved = signal(false);

  readonly savingSetPassword = signal(false);
  readonly setPasswordError = signal<string | null>(null);
  readonly setPasswordSaved = signal(false);

  readonly savingPreferences = signal(false);
  readonly preferencesSaved = signal(false);

  readonly budgetDraft = signal('');
  readonly savingBudget = signal(false);
  readonly budgetSaved = signal(false);
  readonly budgetError = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Pré-preenche o rascunho do teto assim que
   * `BudgetService.load()` (chamado em `ngOnInit`) resolve — mesmo
   * papel do `patchValue` de `personalInfoForm`, mas via Signal porque
   * o teto não é um `FormControl` (campo simples, mesmo padrão do
   * diálogo de teto em `TransactionListComponent`).
   */
  private readonly _syncBudgetDraft = effect(() => {
    this.budgetDraft.set(this.budgetService.monthlyBudget() ?? '');
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: `true` só quando o rascunho não está vazio (vazio é
   * válido — limpa o teto) e não bate no formato decimal aceito —
   * mesma regra/regex já usada no formulário de transação e no diálogo
   * de teto de `TransactionListComponent`.
   */
  readonly budgetInvalid = computed(() => {
    const raw = this.budgetDraft().trim();
    return raw !== '' && !/^\d+([.,]\d{1,2})?$/.test(raw);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Reformata o campo de telefone a cada tecla digitada
   * (`+55 (11) 99999-0001`) — máscara feita à mão (sem lib externa,
   * mesmo padrão de `DropdownSelectComponent`) para não brigar com o
   * design system. `emitEvent: false` evita loop (o próprio `setValue`
   * dispararia `valueChanges`, que nada mais escuta aqui, mas é o
   * padrão seguro).
   */
  protected onPhoneInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const digits = input.value.replace(/\D/g, '').slice(0, 13);
    const formatted = formatPhoneDigits(digits);
    this.personalInfoForm.get('phone')?.setValue(formatted, { emitEvent: false });
    input.value = formatted;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Salva nome/telefone via UpdateProfileUseCase — o telefone
   * é enviado sem a máscara visual (`normalizePhoneForSubmit`, 2026-08-16),
   * só `+` e dígitos; a criptografia acontece na persistência
   * (EncryptedString), transparente pro frontend. Campo vazio omite
   * `phone` do payload em vez de mandar string vazia, para não sobrescrever
   * um telefone já salvo só porque o usuário editou o nome sem tocar nele.
   * Quando `phone` de fato é enviado, marca o item "whatsapp" do
   * checklist de onboarding. Sucesso já tem o banner inline
   * `personalInfoSaved`; erro ganhou toast (build-context-13) — antes
   * ficava mudo, só reativando o botão de salvar.
   */
  savePersonalInfo(): void {
    if (this.personalInfoForm.invalid || this.savingPersonalInfo()) {
      this.personalInfoForm.markAllAsTouched();
      return;
    }

    this.savingPersonalInfo.set(true);
    this.personalInfoSaved.set(false);
    const { name, phone } = this.personalInfoForm.getRawValue();
    const normalizedPhone = normalizePhoneForSubmit(phone);
    this.authService
      .updateProfile({ name, ...(normalizedPhone !== null ? { phone: normalizedPhone } : {}) })
      .subscribe({
        next: () => {
          this.savingPersonalInfo.set(false);
          this.personalInfoSaved.set(true);
          if (normalizedPhone !== null) {
            this.onboarding.markDone('whatsapp');
          }
        },
        error: () => {
          this.savingPersonalInfo.set(false);
          this.showErrorToast('toasts.profile.saveError');
        },
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Troca a senha (exige a atual) via ChangePasswordUseCase —
   * só aparece no template para contas locais (não-OAuth). Reseta o
   * formulário em caso de sucesso, por segurança (não deixa a senha
   * digitada visível na tela).
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
          this.passwordError.set('auth.profile.security.changePasswordError');
        },
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Define a senha local pela primeira vez (conta só-OAuth,
   * `has_password=false`) via SetPasswordUseCase — sem campo de senha
   * atual, diferente de `changePassword()`. Corrige uma lacuna real: a
   * tela escondia todo o formulário de senha para qualquer conta com
   * Google vinculado, mesmo sem senha local nenhuma pra trocar.
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
        this.setPasswordError.set('auth.profile.security.setPasswordError');
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Salva a preferência de idioma — o AuthService já troca o
   * Transloco em runtime assim que a resposta chega (RN-10), sem precisar
   * de lógica extra aqui. Sucesso já tem o banner inline
   * `preferencesSaved`; erro ganhou toast (build-context-13) — antes
   * ficava mudo.
   */
  savePreferences(): void {
    if (this.savingPreferences()) {
      return;
    }

    this.savingPreferences.set(true);
    this.preferencesSaved.set(false);
    this.authService.updateProfile(this.preferencesForm.getRawValue()).subscribe({
      next: () => {
        this.savingPreferences.set(false);
        this.preferencesSaved.set(true);
      },
      error: () => {
        this.savingPreferences.set(false);
        this.showErrorToast('toasts.profile.preferencesError');
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Toast de erro genérico da tela (build-context-13) —
   * `MessageService` é global (`app.config.ts`), o `<p-toast />` mora na
   * raiz (`AppComponent`).
   */
  private showErrorToast(detailKey: string): void {
    this.messageService.add({
      severity: 'error',
      summary: this.transloco.translate('toasts.errorTitle'),
      detail: this.transloco.translate(detailKey),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Salva ou limpa (rascunho vazio) o teto mensal — mesmo
   * `BudgetService` já usado pelo card "Teto mensal" de Transações e
   * pelo modal de configuração rápida do Dashboard; os três ficam em
   * sincronia porque compartilham o mesmo Signal (`monthlyBudget`).
   * Campo novo nesta tela (2026-08-18, pedido do usuário — antes só
   * dava pra editar o teto em Transações).
   */
  saveBudget(): void {
    if (this.budgetInvalid() || this.savingBudget()) {
      return;
    }
    const raw = this.budgetDraft().trim().replace(',', '.');
    this.savingBudget.set(true);
    this.budgetSaved.set(false);
    this.budgetError.set(null);
    this.budgetService.update(raw === '' ? null : raw).subscribe({
      next: () => {
        this.savingBudget.set(false);
        this.budgetSaved.set(true);
        if (raw !== '') {
          this.onboarding.markDone('budget');
        }
      },
      error: () => {
        this.savingBudget.set(false);
        this.budgetError.set('transactions.form.errors.generic');
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Exclui a conta (zona de perigo, já confirmada pelo
   * DeleteAccountPanel) e manda o usuário para /login. Toast de sucesso
   * antes do redirect e de erro (build-context-13) — antes uma falha
   * nessa chamada ficava completamente muda, sem nenhum `error:` no
   * `subscribe`, deixando o usuário sem saber que a conta não foi
   * excluída.
   */
  deleteAccount(): void {
    this.authService.deleteAccount().subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('toasts.successTitle'),
          detail: this.transloco.translate('toasts.account.deleted'),
        });
        this.router.navigateByUrl('/login');
      },
      error: () => {
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('toasts.errorTitle'),
          detail: this.transloco.translate('toasts.account.deleteError'),
        });
      },
    });
  }
}
