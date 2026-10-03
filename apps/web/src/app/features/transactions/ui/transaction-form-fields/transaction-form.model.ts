import { FormBuilder, Validators } from '@angular/forms';
import type {
  PaymentStatus,
  RecurrenceFrequency,
  Transaction,
  TransactionCreateRequest,
  TransactionUpdateRequest,
} from '@amezia/shared-types';

export type AdvancedMode = 'none' | 'installment' | 'recurrence';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-10
 * Descrição: Fábrica do FormGroup usado por `feature/transaction-form`
 * (criação e edição, mesma página pros dois casos). `advancedMode`
 * controla qual bloco (nenhum/parcelado/recorrente) fica ativo —
 * mutuamente exclusivos, mesma regra do backend.
 */
export function createTransactionForm(fb: FormBuilder) {
  const today = new Date().toISOString().slice(0, 10);
  return fb.nonNullable.group({
    categoryId: ['', Validators.required],
    amount: ['', [Validators.required, Validators.pattern(/^\d+([.,]\d{1,2})?$/)]],
    description: ['', [Validators.required, Validators.maxLength(255)]],
    date: [today, Validators.required],
    paymentMethod: ['', Validators.maxLength(1000)],
    status: ['paid' as PaymentStatus, Validators.required],
    advancedMode: ['none' as AdvancedMode],
    installmentTotal: [2, [Validators.min(2), Validators.max(60)]],
    recurrenceFrequency: ['monthly' as RecurrenceFrequency],
    recurrenceEndDate: [''],
  });
}

export type TransactionFormGroup = ReturnType<typeof createTransactionForm>;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Monta o payload de criação a partir do FormGroup —
 * `installment`/`recurrence` só entram quando `advancedMode` seleciona
 * um dos dois (mutuamente exclusivos, build-context-03 §2.7). Normaliza
 * vírgula decimal (`,`) para ponto, já que o campo aceita os dois.
 */
export function buildCreateRequest(form: TransactionFormGroup): TransactionCreateRequest {
  const value = form.getRawValue();
  const payload: TransactionCreateRequest = {
    category_id: value.categoryId,
    amount: value.amount.replace(',', '.'),
    description: value.description,
    date: value.date,
    status: value.status,
    payment_method: value.paymentMethod || null,
  };
  if (value.advancedMode === 'installment') {
    payload.installment = { total: value.installmentTotal };
  } else if (value.advancedMode === 'recurrence') {
    payload.recurrence = {
      frequency: value.recurrenceFrequency,
      end_date: value.recurrenceEndDate || null,
    };
  }
  return payload;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Monta o payload de atualização — sem `installment`/
 * `recurrence` (a edição não muda o mecanismo de parcelamento/
 * recorrência de uma transação já materializada, só seus campos base).
 */
export function buildUpdateRequest(form: TransactionFormGroup): TransactionUpdateRequest {
  const value = form.getRawValue();
  return {
    category_id: value.categoryId,
    amount: value.amount.replace(',', '.'),
    description: value.description,
    date: value.date,
    status: value.status,
    payment_method: value.paymentMethod || null,
  };
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Pré-preenche o formulário a partir de uma transação
 * existente — usado no modo de edição do `transaction-form`.
 */
export function patchFormFromTransaction(form: TransactionFormGroup, transaction: Transaction): void {
  form.patchValue({
    categoryId: transaction.category.public_id,
    amount: transaction.amount,
    description: transaction.description,
    date: transaction.date,
    paymentMethod: transaction.payment_method ?? '',
    status: transaction.status,
  });
}
