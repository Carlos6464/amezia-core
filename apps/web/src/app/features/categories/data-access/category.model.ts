import type { Category, CategoryScope } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Reexporta o contrato de Category de `@amezia/shared-types`
 * (snake_case, espelhando o JSON do Pydantic) — sem camada de tradução
 * de case, conforme decisão registrada no build-context-01 (válida para
 * todos os módulos futuros).
 */
export type { Category, CategoryScope };
