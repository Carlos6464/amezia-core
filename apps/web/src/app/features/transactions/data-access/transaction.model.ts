import type {
  BulkDeleteRequest,
  BulkDeleteResponse,
  CategorySummary,
  Installment,
  InstallmentInput,
  PaginationInfo,
  PaymentStatus,
  RecurrenceFrequency,
  RecurrenceInput,
  RecurrenceRule,
  Transaction,
  TransactionCreateRequest,
  TransactionListResponse,
  TransactionSummary,
  TransactionType,
  TransactionUpdateRequest,
} from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Reexporta os contratos de Transação de `@amezia/shared-types`
 * (snake_case, espelhando o JSON do Pydantic) — mesmo padrão de
 * `category.model.ts` (build-context-02), sem camada de tradução de case.
 */
export type {
  BulkDeleteRequest,
  BulkDeleteResponse,
  CategorySummary,
  Installment,
  InstallmentInput,
  PaginationInfo,
  PaymentStatus,
  RecurrenceFrequency,
  RecurrenceInput,
  RecurrenceRule,
  Transaction,
  TransactionCreateRequest,
  TransactionListResponse,
  TransactionSummary,
  TransactionType,
  TransactionUpdateRequest,
};
