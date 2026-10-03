import type { PaymentStatus } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Filtros de listagem de transações (build-context-03 §2.5) —
 * `status`/`q` vazios (`''`) significam "sem filtro"; `year`/`month`
 * default para o mês corrente (a listagem sempre abre no período atual).
 * Sem filtro de tipo: produto é expense-only (2026-08-14).
 */
export interface TransactionFilters {
  status: PaymentStatus | '';
  year: number;
  month: number;
  q: string;
  page: number;
  pageSize: number;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Filtros default — mês/ano corrente, sem busca, primeira
 * página, 10 por página (valor default do protótipo).
 */
export function defaultTransactionFilters(): TransactionFilters {
  const now = new Date();
  return {
    status: '',
    year: now.getFullYear(),
    month: now.getMonth() + 1,
    q: '',
    page: 1,
    pageSize: 10,
  };
}
