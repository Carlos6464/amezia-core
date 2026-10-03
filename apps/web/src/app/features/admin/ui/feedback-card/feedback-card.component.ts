import { DatePipe } from '@angular/common';
import { Component, computed, input, output } from '@angular/core';
import type { AdminFeedback } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

const PREVIEW_LENGTH = 140;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Item de lista de feedback (build-context-06 §3.3) —
 * avatar, nome/email, canal, prévia da mensagem, data. Clique abre o
 * modal de detalhe (emitido pro pai decidir).
 */
@Component({
  selector: 'app-feedback-card',
  standalone: true,
  imports: [TranslocoModule, DatePipe],
  templateUrl: './feedback-card.component.html',
  styleUrl: './feedback-card.component.css',
})
export class FeedbackCardComponent {
  readonly feedback = input.required<AdminFeedback>();
  readonly cardClick = output<void>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Trunca a mensagem em `PREVIEW_LENGTH` caracteres — a
   * mensagem completa só aparece no modal de detalhe.
   */
  protected readonly preview = computed(() => {
    const message = this.feedback().message;
    return message.length > PREVIEW_LENGTH ? `${message.slice(0, PREVIEW_LENGTH)}…` : message;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Inicial do avatar a partir do nome do usuário —
   * `'?'` quando o usuário já não existe mais (feedback.user null).
   */
  protected readonly initials = computed(() => {
    const name = this.feedback().user?.name ?? '?';
    return name.charAt(0).toUpperCase();
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Classificação NPS (build-context-08) — 0–6 detrator,
   * 7–8 neutro, 9–10 promotor. `null` quando o feedback não tem nota.
   */
  protected readonly npsClass = computed<'detractor' | 'neutral' | 'promoter' | null>(() => {
    const score = this.feedback().nps_score;
    if (score === null) return null;
    if (score >= 9) return 'promoter';
    if (score >= 7) return 'neutral';
    return 'detractor';
  });
}
