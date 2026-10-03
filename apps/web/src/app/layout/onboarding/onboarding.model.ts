/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Identificadores dos itens do checklist "Primeiros passos" —
 * `whatsapp`/`bot_number` são exclusivos deste projeto (não existem no
 * checklist equivalente do projeto irmão).
 */
export type ChecklistItemId =
  | 'first_expense'
  | 'category'
  | 'budget'
  | 'whatsapp'
  | 'bot_number'
  | 'agent'
  | 'tour';

export interface ChecklistItem {
  id: ChecklistItemId;
  labelKey: string;
  route: string | null;
  done: boolean;
}

export type TourStepPosition = 'top' | 'bottom' | 'left' | 'right';

export interface TourStep {
  target: string;
  titleKey: string;
  descriptionKey: string;
  position: TourStepPosition;
}
