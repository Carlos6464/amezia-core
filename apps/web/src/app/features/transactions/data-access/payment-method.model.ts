export const NOT_INFORMED_PAYMENT_METHOD = 'not_informed';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Catálogo fixo de métodos de pagamento — extraído de
 * `payment-method-select.component.ts` (2026-08-10) pra ser reaproveitado
 * também pela coluna "Tipo de pagamento" da tabela de Transações e pela
 * lista de distribuição por tipo de pagamento (`payment-method-
 * distribution-list`), ambas de 2026-09-15, fora de qualquer
 * build-context. `payment_method` no backend continua um `str | null`
 * livre (sem enum/migration) — o valor persistido é sempre um destes
 * `value` (código estável em inglês, mesmo padrão de `PaymentStatus`/
 * `TransactionType`), traduzido na UI via `transactions.paymentMethod.*`.
 * `NOT_INFORMED_PAYMENT_METHOD` não é uma opção selecionável — é a chave
 * que o backend devolve (`GET /reports/payment-method-distribution`)
 * pra transações sem `payment_method` preenchido.
 */
export const PAYMENT_METHODS = [
  { value: 'pix', labelKey: 'transactions.paymentMethod.pix' },
  { value: 'credit_card', labelKey: 'transactions.paymentMethod.creditCard' },
  { value: 'debit_card', labelKey: 'transactions.paymentMethod.debitCard' },
  { value: 'cash', labelKey: 'transactions.paymentMethod.cash' },
  { value: 'bank_transfer', labelKey: 'transactions.paymentMethod.bankTransfer' },
  { value: 'boleto', labelKey: 'transactions.paymentMethod.boleto' },
  { value: 'check', labelKey: 'transactions.paymentMethod.check' },
  { value: 'other', labelKey: 'transactions.paymentMethod.other' },
] as const;

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Resolve a i18n key de rótulo de um `payment_method` bruto
 * — `null`/vazio e `NOT_INFORMED_PAYMENT_METHOD` caem no mesmo rótulo
 * "Não informado"; um valor fora do catálogo (não deveria acontecer via
 * UI, já que o combobox só oferece os 8 valores fixos) cai no mesmo
 * rótulo por segurança, em vez de mostrar o código bruto em inglês.
 */
export function paymentMethodLabelKey(value: string | null | undefined): string {
  if (!value || value === NOT_INFORMED_PAYMENT_METHOD) {
    return 'transactions.paymentMethod.notInformed';
  }
  return PAYMENT_METHODS.find((method) => method.value === value)?.labelKey ?? 'transactions.paymentMethod.notInformed';
}
