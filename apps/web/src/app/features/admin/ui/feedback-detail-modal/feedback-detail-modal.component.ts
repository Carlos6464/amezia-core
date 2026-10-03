import { DatePipe } from '@angular/common';
import { Component, computed, input, output } from '@angular/core';
import type { AdminFeedback } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Modal de detalhe do feedback (build-context-06 §3.3) —
 * mensagem completa (o card só mostra uma prévia truncada), somente
 * leitura.
 */
@Component({
  selector: 'app-feedback-detail-modal',
  standalone: true,
  imports: [TranslocoModule, DatePipe],
  templateUrl: './feedback-detail-modal.component.html',
  styleUrl: './feedback-detail-modal.component.css',
})
export class FeedbackDetailModalComponent {
  readonly feedback = input.required<AdminFeedback>();
  readonly closeModal = output<void>();

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

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Fecha o modal só quando o clique foi direto no overlay
   * (não borbulhado do card) — substitui `stopPropagation()` no card
   * interno, que o linter de acessibilidade rejeitaria (handler de
   * clique sem par de teclado num elemento não focável).
   */
  protected onOverlayClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.closeModal.emit();
    }
  }
}
