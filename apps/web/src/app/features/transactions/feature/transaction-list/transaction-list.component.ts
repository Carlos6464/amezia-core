import { Component, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { DialogModule } from 'primeng/dialog';
import type { PaymentStatus, Transaction } from '@amezia/shared-types';

import { BreakpointService } from '../../../../core/viewport/breakpoint.service';
import { OnboardingService } from '../../../../layout/onboarding/onboarding.service';
import { BudgetService } from '../../data-access/budget.service';
import { TransactionService } from '../../data-access/transaction.service';
import { PaymentMethodSelectComponent } from '../../ui/payment-method-select/payment-method-select.component';
import { TransactionFilterBarComponent } from '../../ui/transaction-filter-bar/transaction-filter-bar.component';
import { TransactionStatsStripComponent } from '../../ui/transaction-stats-strip/transaction-stats-strip.component';
import { TransactionTableComponent } from '../../ui/transaction-table/transaction-table.component';

type ViewState = 'loading' | 'error' | 'empty' | 'no-results' | 'list';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Página smart de Transações — orquestra TransactionService,
 * BudgetService, filtros (busca sob demanda + período instantâneo),
 * seleção para exclusão em lote, e os estados de tela do build-context-03
 * §3.3 (loading/vazio/filtros ativos/erro/paginado/responsivo).
 */
@Component({
  selector: 'app-transaction-list',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    TranslocoModule,
    ConfirmDialogModule,
    DialogModule,
    PaymentMethodSelectComponent,
    TransactionFilterBarComponent,
    TransactionStatsStripComponent,
    TransactionTableComponent,
  ],
  templateUrl: './transaction-list.component.html',
  styleUrl: './transaction-list.component.css',
})
export class TransactionListComponent {
  protected readonly transactionService = inject(TransactionService);
  protected readonly budgetService = inject(BudgetService);
  protected readonly breakpoint = inject(BreakpointService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly messageService = inject(MessageService);
  private readonly onboarding = inject(OnboardingService);
  private readonly transloco = inject(TranslocoService);
  private readonly router = inject(Router);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Referência ao componente de filtro — no mobile, o botão
   * que abre o bottom sheet fica no cabeçalho da página (ao lado do
   * título), não mais dentro do próprio componente, então precisa de um
   * jeito de acioná-lo de fora.
   */
  @ViewChild(TransactionFilterBarComponent) filterBar?: TransactionFilterBarComponent;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Abre o bottom sheet de filtro a partir do botão no
   * cabeçalho da página (mobile).
   */
  openFilterSheet(): void {
    this.filterBar?.openSheet();
  }

  readonly draftQ = signal('');
  readonly draftStatus = signal<PaymentStatus | ''>('');
  readonly selectedIds = signal<ReadonlySet<string>>(new Set());

  readonly budgetDialogVisible = signal(false);
  readonly budgetDraft = signal('');
  readonly budgetSaving = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: `true` só quando o rascunho não está vazio (vazio é
   * válido — limpa o teto, ver `saveBudget`) e não bate no formato
   * decimal aceito (mesmo padrão de `amount` do form de transação) —
   * controla o erro inline e desabilita "Salvar". Bug real relatado
   * pelo usuário: o campo não validava nada antes, e um valor rejeitado
   * pelo backend falhava em silêncio (`error: () =>
   * this.budgetSaving.set(false)`, sem nenhuma mensagem).
   */
  readonly budgetInvalid = computed(() => {
    const raw = this.budgetDraft().trim();
    return raw !== '' && !/^\d+([.,]\d{1,2})?$/.test(raw);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Transação pendente aguardando confirmação de pagamento no
   * diálogo "Pagar" — `null` quando o diálogo está fechado. Guarda a
   * transação inteira (mesmo padrão de `groupDeleteTarget`) porque o
   * diálogo mostra descrição/valor dela.
   */
  readonly payDialogTarget = signal<Transaction | null>(null);
  readonly payDateDraft = signal('');
  readonly payPaymentMethodDraft = signal('');
  readonly payReceiptFile = signal<File | null>(null);
  readonly paySaving = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Transação em grupo (recorrente ou parcelada) aguardando a
   * escolha do usuário entre excluir só esta ou todas do grupo — `null`
   * quando o diálogo está fechado. Guarda a transação inteira (não só o
   * `public_id`) porque o diálogo mostra a descrição dela. Nasceu só
   * para recorrência (2026-08-10) e foi generalizada para parcelamento
   * (2026-08-11) — o usuário pediu a mesma escolha "excluir todas" que
   * já existia para recorrência, só que para parcelas.
   */
  readonly groupDeleteTarget = signal<Transaction | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Qual dos dois agrupamentos mutuamente exclusivos a
   * transação em `groupDeleteTarget` pertence — decide os textos do
   * diálogo (header/mensagem/rótulo do botão "excluir todas"). `null`
   * só quando o diálogo está fechado.
   */
  readonly groupDeleteKind = computed<'recurring' | 'installment' | null>(() => {
    const transaction = this.groupDeleteTarget();
    if (!transaction) {
      return null;
    }
    return transaction.is_recurring ? 'recurring' : transaction.installment ? 'installment' : null;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: `true` quando algum filtro além do período padrão está
   * ativo — usado para diferenciar "vazio" de "sem resultado de busca".
   */
  private readonly hasActiveFilters = computed(() => {
    const filters = this.transactionService.filters();
    return filters.q !== '' || filters.status !== '';
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Primeiro item exibido na página atual — 0 quando a
   * listagem está vazia (evita "Mostrando 1-0 de 0").
   */
  readonly showingFrom = computed(() => {
    const pagination = this.transactionService.pagination();
    return pagination.total === 0 ? 0 : (pagination.page - 1) * pagination.page_size + 1;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Último item exibido na página atual — nunca passa do
   * total (última página pode ter menos itens que `pageSize`).
   */
  readonly showingTo = computed(() => {
    const pagination = this.transactionService.pagination();
    return Math.min(pagination.page * pagination.page_size, pagination.total);
  });

  readonly viewState = computed<ViewState>(() => {
    if (this.transactionService.loading()) {
      return 'loading';
    }
    if (this.transactionService.error()) {
      return 'error';
    }
    if (this.transactionService.transactions().length === 0) {
      return this.hasActiveFilters() ? 'no-results' : 'empty';
    }
    return 'list';
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Dispara o carregamento inicial da listagem e do teto
   * mensal ao montar a página.
   */
  constructor() {
    this.transactionService.load();
    this.budgetService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Recarrega a listagem — botão "Tentar novamente" do
   * estado de erro.
   */
  retry(): void {
    this.transactionService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Aplica os filtros de busca/status digitados na
   * filter-bar — o período (ano/mês) já foi aplicado antes, via
   * `onPeriodChange`.
   */
  search(): void {
    this.transactionService.updateFilters({
      q: this.draftQ(),
      status: this.draftStatus(),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Volta busca/status/período para o padrão (mês corrente,
   * sem filtros) — botão "Limpar" da filter-bar.
   */
  clearFilters(): void {
    this.draftQ.set('');
    this.draftStatus.set('');
    this.transactionService.resetFilters();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Navegação de período (setas da filter-bar) — instantânea,
   * não espera o botão "Buscar".
   */
  changePeriod(period: { year: number; month: number }): void {
    this.transactionService.updateFilters(period);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Navega para a página de edição completa da transação.
   */
  editTransaction(transaction: Transaction): void {
    void this.router.navigate(['/transactions', transaction.public_id, 'edit']);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Abre o diálogo "Pagar" pré-preenchido com a data de hoje
   * e a forma de pagamento já cadastrada na transação (se houver) —
   * acionado pelo botão de check verde da tabela, visível só quando
   * `status === 'pending'`. Forma de pagamento é opcional, mesmo padrão
   * do formulário de criação/edição (`transaction-form.model.ts`).
   */
  openPayDialog(transaction: Transaction): void {
    this.payDialogTarget.set(transaction);
    this.payDateDraft.set(new Date().toISOString().slice(0, 10));
    this.payPaymentMethodDraft.set(transaction.payment_method ?? '');
    this.payReceiptFile.set(null);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Fecha o diálogo "Pagar" sem salvar — botão Cancelar ou
   * dispensar o diálogo (máscara/Esc).
   */
  onPayDialogVisibleChange(visible: boolean): void {
    if (!visible) {
      this.payDialogTarget.set(null);
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Guarda o comprovante escolhido no `<input type="file">`
   * do diálogo "Pagar" — só é enviado de fato em `confirmPay`, depois que
   * o status/data de pagamento já foram salvos (a transação precisa
   * existir com `public_id`, o que já é o caso aqui — diferente da
   * criação, não há "staging" à espera de um id).
   */
  onPayFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      this.payReceiptFile.set(file);
    }
    input.value = '';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Confirma o pagamento — marca `status: 'paid'` + `paid_at`
   * + forma de pagamento (opcional, pedido do usuário — o modal não
   * tinha esse campo antes, só a data), depois envia o comprovante se
   * um foi escolhido, e por fim recarrega a listagem (mesmo motivo de
   * `remove`/`bulkRemove`: `summary`/paginação não se recalculam
   * sozinhos no cliente).
   */
  confirmPay(): void {
    const transaction = this.payDialogTarget();
    const paidAt = this.payDateDraft();
    if (!transaction || !paidAt) {
      return;
    }
    this.paySaving.set(true);
    this.transactionService
      .update(transaction.public_id, {
        status: 'paid',
        paid_at: paidAt,
        payment_method: this.payPaymentMethodDraft() || null,
      })
      .subscribe({
        next: () => {
          const file = this.payReceiptFile();
          if (file) {
            this.transactionService.uploadReceipt(transaction.public_id, file).subscribe({
              next: () => this.finishPay(),
              error: () => this.finishPay(),
            });
          } else {
            this.finishPay();
          }
        },
        error: () => {
          this.paySaving.set(false);
          this.showErrorToast('transactions.form.errors.generic');
        },
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Encerra o fluxo de pagamento — fecha o diálogo, mostra o
   * toast de sucesso (build-context-13, antes o modal só fechava em
   * silêncio) e recarrega a listagem para refletir o novo
   * status/comprovante.
   */
  private finishPay(): void {
    this.paySaving.set(false);
    this.payDialogTarget.set(null);
    this.showSuccessToast('toasts.transaction.paid');
    this.transactionService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Decide qual confirmação mostrar antes de excluir uma
   * transação — recorrente ou parcelada abre o diálogo de 3 botões
   * (`groupDeleteTarget`, escolha entre "só esta"/"todas"); uma
   * transação avulsa usa o `ConfirmDialog` padrão de 2 botões do
   * PrimeNG.
   */
  confirmDelete(transaction: Transaction): void {
    if (transaction.is_recurring || transaction.installment !== null) {
      this.groupDeleteTarget.set(transaction);
      return;
    }
    this.confirmationService.confirm({
      header: this.transloco.translate('transactions.confirmDelete.header'),
      message: this.transloco.translate('transactions.confirmDelete.message', {
        description: transaction.description,
      }),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: this.transloco.translate('transactions.confirmDelete.accept'),
      rejectLabel: this.transloco.translate('transactions.confirmDelete.reject'),
      acceptButtonProps: { severity: 'danger' },
      rejectButtonProps: { severity: 'secondary', outlined: true },
      accept: () =>
        this.transactionService.remove(transaction.public_id).subscribe({
          next: () => this.showSuccessToast('toasts.transaction.deleted'),
          error: () => this.showErrorToast('toasts.transaction.deleteError'),
        }),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Fecha o diálogo de exclusão em grupo sem excluir nada —
   * acionado pelo botão Cancelar ou ao dispensar o diálogo (máscara/Esc).
   */
  onGroupDeleteVisibleChange(visible: boolean): void {
    if (!visible) {
      this.groupDeleteTarget.set(null);
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Resolve a escolha do diálogo de exclusão em grupo —
   * `'single'` exclui só a transação clicada (mesmo comportamento de
   * sempre); `'all'` manda `all_occurrences=true`, que no backend apaga
   * o grupo inteiro (todo o histórico da regra + desativa a regra, numa
   * recorrente; todas as parcelas do `installment_group_id`, numa
   * parcelada) — a distinção de qual dos dois casos é fica por conta do
   * backend, o frontend só manda o mesmo flag nos dois. Toast de
   * sucesso/erro varia a chave conforme o escopo, pra deixar claro se
   * foi uma transação só ou o grupo inteiro que saiu.
   */
  deleteGroupTransaction(scope: 'single' | 'all'): void {
    const transaction = this.groupDeleteTarget();
    if (!transaction) {
      return;
    }
    this.groupDeleteTarget.set(null);
    this.transactionService
      .remove(transaction.public_id, { allOccurrences: scope === 'all' })
      .subscribe({
        next: () =>
          this.showSuccessToast(
            scope === 'all' ? 'toasts.transaction.groupDeleted' : 'toasts.transaction.deleted',
          ),
        error: () =>
          this.showErrorToast(
            scope === 'all' ? 'toasts.transaction.groupDeleteError' : 'toasts.transaction.deleteError',
          ),
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Alterna a seleção de uma linha — alimenta a exclusão em
   * lote (ex.: todas as parcelas de uma mesma compra).
   */
  toggleSelect(publicId: string): void {
    this.selectedIds.update((current) => {
      const next = new Set(current);
      if (next.has(publicId)) {
        next.delete(publicId);
      } else {
        next.add(publicId);
      }
      return next;
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Confirma e executa a exclusão em lote das linhas
   * selecionadas — limpa a seleção ao final, sucesso ou erro. Toast de
   * sucesso informa quantas transações saíram; erro não limpa a
   * seleção, pra o usuário poder tentar de novo sem reselecionar tudo.
   */
  confirmBulkDelete(): void {
    const ids = Array.from(this.selectedIds());
    if (ids.length === 0) {
      return;
    }
    this.confirmationService.confirm({
      header: this.transloco.translate('transactions.bulkDelete.header'),
      message: this.transloco.translate('transactions.bulkDelete.message', { count: ids.length }),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: this.transloco.translate('transactions.confirmDelete.accept'),
      rejectLabel: this.transloco.translate('transactions.confirmDelete.reject'),
      acceptButtonProps: { severity: 'danger' },
      rejectButtonProps: { severity: 'secondary', outlined: true },
      accept: () => {
        this.transactionService.bulkRemove(ids).subscribe({
          next: () => {
            this.selectedIds.set(new Set());
            this.showSuccessToast('toasts.transaction.bulkDeleted', { count: ids.length });
          },
          error: () => this.showErrorToast('toasts.transaction.bulkDeleteError'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Navega para outra página mantendo os filtros atuais.
   */
  goToPage(page: number): void {
    this.transactionService.goToPage(page);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Abre o diálogo de definir/editar o teto mensal,
   * pré-preenchido com o valor atual (vazio se ainda não configurado).
   */
  openBudgetDialog(): void {
    this.budgetDraft.set(this.budgetService.monthlyBudget() ?? '');
    this.budgetDialogVisible.set(true);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Salva o teto mensal (`null` se o campo for deixado
   * vazio, o que limpa o teto) e recarrega a listagem pra refletir o
   * novo `summary.budget_used_percentage`. Definir um teto de verdade
   * (não limpar) marca o item "budget" do checklist de onboarding.
   * Toast de sucesso (build-context-13) — antes o modal só fechava em
   * silêncio.
   */
  saveBudget(): void {
    if (this.budgetInvalid()) {
      return;
    }
    const raw = this.budgetDraft().trim().replace(',', '.');
    this.budgetSaving.set(true);
    this.budgetService.update(raw === '' ? null : raw).subscribe({
      next: () => {
        this.budgetSaving.set(false);
        this.budgetDialogVisible.set(false);
        this.showSuccessToast('toasts.budget.saved');
        this.transactionService.load();
        if (raw !== '') {
          this.onboarding.markDone('budget');
        }
      },
      error: () => {
        this.budgetSaving.set(false);
        this.showErrorToast('transactions.form.errors.generic');
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Erro de servidor (teto mensal, confirmação de pagamento
   * ou exclusão de transação/grupo/lote) vira toast — antes falhava em
   * silêncio, só reativando o botão de salvar sem dizer nada ao
   * usuário. `MessageService` é global (`app.config.ts`), o
   * `<p-toast />` mora na raiz (`AppComponent`). `params` interpola
   * placeholders da chave de tradução (ex.: `{{count}}`).
   */
  private showErrorToast(detailKey: string, params?: Record<string, unknown>): void {
    this.messageService.add({
      severity: 'error',
      summary: this.transloco.translate('transactions.form.errors.toastTitle'),
      detail: this.transloco.translate(detailKey, params),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Confirmação de sucesso em toast para ações que antes
   * ficavam mudas (exclusão de transação/grupo/lote, build-context-13)
   * — o usuário só percebia pelo efeito indireto (item sumiu da lista).
   * `params` interpola placeholders da chave de tradução (ex.:
   * `{{count}}`).
   */
  private showSuccessToast(detailKey: string, params?: Record<string, unknown>): void {
    this.messageService.add({
      severity: 'success',
      summary: this.transloco.translate('toasts.successTitle'),
      detail: this.transloco.translate(detailKey, params),
    });
  }
}
