import { Component, input, output } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';
import { TranslocoModule } from '@jsverse/transloco';
import type { PaymentStatus, RecurrenceFrequency, Transaction } from '@amezia/shared-types';

import { CategorySelectComponent } from '../category-select/category-select.component';
import { PaymentMethodSelectComponent } from '../payment-method-select/payment-method-select.component';
import type { AdvancedMode, TransactionFormGroup } from './transaction-form.model';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-10
 * Descrição: Corpo do formulário de transação, usado por
 * `feature/transaction-form` (criação e edição, mesma página pros dois
 * casos). Componente burro: só reflete o `FormGroup` recebido, não chama
 * a API.
 */
@Component({
  selector: 'app-transaction-form-fields',
  standalone: true,
  imports: [ReactiveFormsModule, TranslocoModule, CategorySelectComponent, PaymentMethodSelectComponent],
  templateUrl: './transaction-form-fields.component.html',
  styleUrl: './transaction-form-fields.component.css',
})
export class TransactionFormFieldsComponent {
  form = input.required<TransactionFormGroup>();
  editingTransaction = input<Transaction | null>(null);
  receiptUploading = input(false);
  stagedReceiptFile = input<File | null>(null);

  // Modo edição: upload imediato (a transação já existe, tem public_id).
  // Modo criação: o arquivo só é "staged" aqui — o pai decide quando
  // efetivamente enviar (junto com a criação da transação).
  receiptFileSelected = output<File>();
  removeReceipt = output<void>();
  removeStagedReceipt = output<void>();

  readonly statusOptions: PaymentStatus[] = ['pending', 'paid'];
  readonly frequencyOptions: RecurrenceFrequency[] = ['weekly', 'monthly', 'yearly'];

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Muda o modo avançado (nenhum/parcelado/recorrente) —
   * mutuamente exclusivos, mesma regra do backend (build-context-03 §2.7).
   */
  setAdvancedMode(mode: AdvancedMode): void {
    this.form().controls.advancedMode.setValue(mode);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Muda o status de pagamento a partir das pílulas
   * clicáveis (Pendente/Pago).
   */
  setStatus(status: PaymentStatus): void {
    this.form().controls.status.setValue(status);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Chave i18n do rótulo da seção de Status — em modo
   * parcelado/recorrente, na criação (nunca editando uma transação já
   * existente, onde o conceito de "1ª parcela" não se aplica), deixa
   * explícito que a escolha vale só pra 1ª parcela/ocorrência: as
   * demais nascem sempre pendentes, mesmo que o usuário marque "pago"
   * aqui (regra espelhada no backend — `CreateTransactionUseCase`/
   * `GenerateDueRecurrencesUseCase`, ajuste de 2026-08-09).
   */
  statusLabelKey(): string {
    if (this.editingTransaction()) {
      return 'transactions.form.status';
    }
    const mode = this.form().controls.advancedMode.value;
    if (mode === 'installment') {
      return 'transactions.form.statusFirstInstallment';
    }
    if (mode === 'recurrence') {
      return 'transactions.form.statusFirstOccurrence';
    }
    return 'transactions.form.status';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Chave i18n do aviso mostrado junto ao Status e ao
   * comprovante quando o modo avançado é parcelado/recorrente na
   * criação — `null` quando não há nada a avisar (modo "nenhum" ou
   * editando uma transação existente).
   */
  advancedStatusHintKey(): string | null {
    if (this.editingTransaction()) {
      return null;
    }
    const mode = this.form().controls.advancedMode.value;
    if (mode === 'installment') {
      return 'transactions.form.installmentStatusHint';
    }
    if (mode === 'recurrence') {
      return 'transactions.form.recurrenceStatusHint';
    }
    return null;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Repassa o arquivo escolhido no `<input type="file">` para
   * o componente pai — que decide se envia na hora (edição, transação já
   * tem `public_id`) ou guarda pra enviar assim que a transação for
   * criada (status "pago" na criação, ver build-context-03 §2.8).
   */
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      this.receiptFileSelected.emit(file);
    }
    input.value = '';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: `true` quando o campo tem erro de validação E já foi
   * tocado — controla a borda vermelha e a mensagem inline de cada
   * campo. Sem checar `touched`, todo campo obrigatório nasceria "errado"
   * antes do usuário digitar qualquer coisa. Mesmo padrão já usado em
   * `AdminWhatsappPageComponent.fieldInvalid` (2026-08-15) — bug real
   * relatado pelo usuário aqui também: `markAllAsTouched()` já rodava no
   * `submit()` do form pai, mas nada no template lia `invalid`/`touched`.
   */
  protected fieldInvalid(name: keyof TransactionFormGroup['controls']): boolean {
    const control = this.form().get(name);
    return !!control && control.invalid && control.touched;
  }
}
