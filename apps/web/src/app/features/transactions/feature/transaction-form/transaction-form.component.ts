import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { MessageService } from 'primeng/api';
import type { Transaction } from '@amezia/shared-types';

import { OnboardingService } from '../../../../layout/onboarding/onboarding.service';
import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { CategoriesService } from '../../../categories/data-access/categories.service';
import { RecurrenceService } from '../../data-access/recurrence.service';
import { TransactionService } from '../../data-access/transaction.service';
import { TransactionFormFieldsComponent } from '../../ui/transaction-form-fields/transaction-form-fields.component';
import {
  buildCreateRequest,
  buildUpdateRequest,
  createTransactionForm,
  patchFormFromTransaction,
} from '../../ui/transaction-form-fields/transaction-form.model';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Formulário completo de criação/edição — mapeia
 * `expense-form/index.html` (build-context-03 §3.2). Rota única
 * (`/transactions/new` e `/transactions/:publicId/edit`) alimentada por
 * `GetTransactionUseCase` no modo edição. Mostra um banner de cancelar
 * recorrência quando a transação em edição foi gerada automaticamente.
 */
@Component({
  selector: 'app-transaction-form',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoModule,
    TransactionFormFieldsComponent,
    BrlAmountPipe,
  ],
  templateUrl: './transaction-form.component.html',
  styleUrl: './transaction-form.component.css',
})
export class TransactionFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly transactionService = inject(TransactionService);
  protected readonly recurrenceService = inject(RecurrenceService);
  protected readonly categoriesService = inject(CategoriesService);
  private readonly onboarding = inject(OnboardingService);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);

  readonly form = createTransactionForm(this.fb);
  readonly saving = signal(false);
  readonly loading = signal(false);
  readonly transaction = signal<Transaction | null>(null);
  readonly receiptUploading = signal(false);
  readonly stagedReceiptFile = signal<File | null>(null);
  readonly publicId = signal<string | null>(null);

  readonly isEditMode = computed(() => this.publicId() !== null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Destino de "voltar"/"cancelar"/pós-salvar — lê `?from=`
   * da query string (setado pelo FAB do Dashboard ou da listagem, ver
   * `AppShellComponent.quickAddOrigin`) pra devolver o usuário pro mesmo
   * lugar de onde ele veio. Sem `from` (ex.: edição, sempre aberta a
   * partir da listagem), volta pra `/transactions` como sempre foi.
   */
  readonly backTarget = computed(() =>
    this.route.snapshot.queryParamMap.get('from') === 'dashboard' ? '/dashboard' : '/transactions',
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Valores do formulário como Signal (via `toSignal`) —
   * alimenta o card "Resumo em tempo real" da coluna lateral sem
   * precisar de um `effect()` manual.
   */
  readonly formValue = toSignal(this.form.valueChanges, { initialValue: this.form.getRawValue() });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Categoria selecionada no formulário — usada no preview
   * (nome/cor) sem esperar o próximo carregamento da lista.
   */
  readonly selectedCategory = computed(() =>
    this.categoriesService
      .categories()
      .find((category) => category.public_id === this.formValue().categoryId),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Encontra a RecurrenceRule que gerou a transação em
   * edição — a API não expõe o id da regra na transação, então o
   * casamento é feito pelos campos que a regra sempre copia 1:1 ao
   * materializar uma ocorrência (categoria, descrição, valor). É uma
   * heurística deliberada, não uma referência armazenada.
   */
  readonly matchingRecurrence = computed(() => {
    const current = this.transaction();
    if (!current || !current.is_recurring) {
      return null;
    }
    return (
      this.recurrenceService
        .recurrences()
        .find(
          (rule) =>
            rule.category.public_id === current.category.public_id &&
            rule.description === current.description &&
            rule.amount === current.amount,
        ) ?? null
    );
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Detecta o modo edição pelo parâmetro de rota
   * `:publicId` e, se presente, carrega a transação e pré-preenche o
   * formulário. Também carrega categorias e recorrências ativas
   * (necessárias para o select e o banner de recorrência).
   */
  constructor() {
    this.categoriesService.load();
    this.recurrenceService.load();

    const publicId = this.route.snapshot.paramMap.get('publicId');
    if (publicId) {
      this.publicId.set(publicId);
      this.loadTransaction(publicId);
    }
  }

  private loadTransaction(publicId: string): void {
    this.loading.set(true);
    this.transactionService.get(publicId).subscribe({
      next: (transaction) => {
        this.transaction.set(transaction);
        patchFormFromTransaction(this.form, transaction);
        this.loading.set(false);
      },
      error: () => {
        this.showErrorToast('transactions.form.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Erro de servidor (não de validação de campo — esses já
   * ficam visíveis inline em `TransactionFormFieldsComponent`) vira
   * toast, não mais o banner `.form-msg.error` que existia no topo do
   * form — pedido do usuário. `MessageService` é global (`app.config.ts`),
   * o `<p-toast />` mora na raiz (`AppComponent`). Corpo extraído para
   * `addToast` (build-context-13) para reaproveitar a montagem da
   * mensagem com os novos toasts de sucesso/aviso.
   */
  private showErrorToast(detailKey: string): void {
    this.addToast('error', 'transactions.form.errors.toastTitle', detailKey);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Helper genérico de toast (build-context-13) — reúne a
   * montagem de `severity`/`summary`/`detail` usada tanto pelo erro
   * genérico do form (`showErrorToast`, chave de título própria) quanto
   * pelos novos toasts de sucesso/erro/aviso do namespace `toasts.*`
   * (comprovante, cancelamento de recorrência).
   */
  private addToast(severity: 'success' | 'error' | 'warn', summaryKey: string, detailKey: string): void {
    this.messageService.add({
      severity,
      summary: this.transloco.translate(summaryKey),
      detail: this.transloco.translate(detailKey),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Cria ou atualiza a transação conforme o modo. Na criação,
   * se um comprovante foi selecionado antes de salvar (status "pago" —
   * ver `onReceiptFileSelected`), envia logo em seguida, antes de voltar
   * pra listagem — falha no upload não impede a navegação, a transação
   * já foi criada com sucesso. Criar (não editar) marca o item
   * "first_expense" do checklist de onboarding. Falha no upload do
   * comprovante (build-context-13) antes era engolida de propósito
   * (`error: () => this.finishSubmit()`, sem avisar nada) — agora mostra
   * um toast de aviso (`warn`, não `error`) informando que a transação
   * em si foi salva, só o comprovante que não foi, já que navegar
   * embora sem dizer isso escondia a falha por completo. Toast de
   * sucesso (build-context-13) varia a chave conforme criação/edição —
   * disparado antes do upload do comprovante pra sempre aparecer,
   * mesmo se o upload falhar depois.
   */
  submit(): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);

    const publicId = this.publicId();
    const request$ = publicId
      ? this.transactionService.update(publicId, buildUpdateRequest(this.form))
      : this.transactionService.create(buildCreateRequest(this.form));

    request$.subscribe({
      next: (transaction) => {
        if (!publicId) {
          this.onboarding.markDone('first_expense');
        }
        this.addToast(
          'success',
          'toasts.successTitle',
          publicId ? 'toasts.transaction.updated' : 'toasts.transaction.created',
        );
        const staged = this.stagedReceiptFile();
        if (!publicId && staged) {
          this.transactionService.uploadReceipt(transaction.public_id, staged).subscribe({
            next: () => this.finishSubmit(),
            error: () => {
              this.addToast('warn', 'toasts.warnTitle', 'toasts.receipt.uploadErrorAfterSave');
              this.finishSubmit();
            },
          });
        } else {
          this.finishSubmit();
        }
      },
      error: () => {
        this.saving.set(false);
        this.showErrorToast('transactions.form.errors.generic');
      },
    });
  }

  private finishSubmit(): void {
    this.saving.set(false);
    void this.router.navigate([this.backTarget()]);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Decide o que fazer com o arquivo escolhido — em modo
   * edição a transação já existe, então envia na hora; em modo criação
   * só guarda o arquivo (`stagedReceiptFile`), o envio de fato acontece
   * em `submit()`, logo após a transação ser criada. Toast de
   * sucesso/erro (build-context-13) no caminho de edição — antes ficava
   * mudo nos dois casos, o usuário só percebia pelo preview do
   * comprovante aparecer (ou não).
   */
  onReceiptFileSelected(file: File): void {
    const publicId = this.publicId();
    if (!publicId) {
      this.stagedReceiptFile.set(file);
      return;
    }
    this.receiptUploading.set(true);
    this.transactionService.uploadReceipt(publicId, file).subscribe({
      next: (updated) => {
        this.transaction.set(updated);
        this.receiptUploading.set(false);
        this.addToast('success', 'toasts.successTitle', 'toasts.receipt.uploaded');
      },
      error: () => {
        this.receiptUploading.set(false);
        this.addToast('error', 'toasts.errorTitle', 'toasts.receipt.uploadError');
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Remove o comprovante anexado à transação em edição.
   * Toast de sucesso/erro (build-context-13) — antes ficava mudo nos
   * dois casos.
   */
  removeReceipt(): void {
    const publicId = this.publicId();
    if (!publicId) {
      return;
    }
    this.transactionService.deleteReceipt(publicId).subscribe({
      next: (updated) => {
        this.transaction.set(updated);
        this.addToast('success', 'toasts.successTitle', 'toasts.receipt.removed');
      },
      error: () => this.addToast('error', 'toasts.errorTitle', 'toasts.receipt.removeError'),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Descarta o arquivo escolhido antes da transação existir
   * (modo criação) — o usuário pode trocar de ideia antes de salvar.
   */
  removeStagedReceipt(): void {
    this.stagedReceiptFile.set(null);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Cancela a recorrência que gerou a transação em edição —
   * não afeta o histórico já materializado, só impede novas ocorrências.
   * Toast de sucesso/erro (build-context-13) — ação destrutiva que
   * antes não confirmava nada ao usuário.
   */
  cancelRecurrence(): void {
    const rule = this.matchingRecurrence();
    if (!rule) {
      return;
    }
    this.recurrenceService.cancel(rule.public_id).subscribe({
      next: () => this.addToast('success', 'toasts.successTitle', 'toasts.recurrence.cancelled'),
      error: () => this.addToast('error', 'toasts.errorTitle', 'toasts.recurrence.cancelError'),
    });
  }
}
