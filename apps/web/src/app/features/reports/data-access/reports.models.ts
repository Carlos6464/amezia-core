import type {
  CategoryDistributionItem,
  FinancialSummary,
  MonthlyEvolutionPoint,
  MonthlyPaidPendingPoint,
  NarrativeQueuedResponse,
  NarrativeRequest,
  PaginatedTransactionsResponse,
  PaymentMethodDistributionItem,
  ReportNarrativeFailedEvent,
  ReportNarrativeReadyEvent,
  ReportTransaction,
} from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Reexporta os contratos de Relatórios de `@amezia/shared-types`
 * (snake_case, espelhando o JSON do Pydantic) — mesmo padrão de
 * `transaction.model.ts`/`category.model.ts`, sem camada de tradução de
 * case.
 */
export type {
  CategoryDistributionItem,
  FinancialSummary,
  MonthlyEvolutionPoint,
  MonthlyPaidPendingPoint,
  NarrativeQueuedResponse,
  NarrativeRequest,
  PaginatedTransactionsResponse,
  PaymentMethodDistributionItem,
  ReportNarrativeFailedEvent,
  ReportNarrativeReadyEvent,
  ReportTransaction,
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Estado assíncrono do card de narrativa IA (build-context-05
 * §3.4) — os 5 estados descritos na spec, condensados num único Signal.
 * `limit_reached` (2026-09-11) foi separado de `failed`: o backend já
 * publicava `report.narrative.failed` com `payload.reason` distinguindo
 * "limite mensal do plano atingido" de "provider de IA indisponível",
 * mas o frontend ignorava o motivo e mostrava a mesma mensagem genérica
 * de "tente novamente" pros dois casos — enganoso quando repetir não
 * resolve nada até o próximo ciclo ou um upgrade de plano.
 */
export type NarrativeState = 'idle' | 'loading' | 'ready' | 'throttled' | 'failed' | 'limit_reached';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Filtro de categoria da tela de Reports — `''` significa
 * "sem filtro" (mesmo padrão de `TransactionFilters` do módulo de
 * Transações). Sem filtro de tipo: produto é expense-only (2026-08-14).
 */
export interface ReportsFilters {
  categoryId: string;
}

export interface ReportsDateRange {
  dateFrom: string;
  dateTo: string;
}
