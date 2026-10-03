import type { Feedback, FeedbackChannel, FeedbackCreateRequest, FeedbackType } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Reexporta o contrato de Feedback de `@amezia/shared-types`
 * (snake_case, espelhando o JSON do Pydantic) — sem camada de tradução
 * de case, mesmo padrão já usado por Category/Transaction.
 */
export type { Feedback, FeedbackChannel, FeedbackCreateRequest, FeedbackType };
