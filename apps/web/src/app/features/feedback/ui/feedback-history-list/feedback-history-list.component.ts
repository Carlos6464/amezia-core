import { Component, inject, input } from '@angular/core';
import type { Feedback } from '@amezia/shared-types';
import { TranslocoService, TranslocoModule } from '@jsverse/transloco';

const INTL_LOCALE_BY_LANG: Record<string, string> = { 'pt-BR': 'pt-BR', en: 'en-US' };
const PREVIEW_LENGTH = 140;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Histórico de feedbacks enviados pelo próprio usuário
 * (build-context-08 §3.1) — item por linha (ícone + assunto + prévia +
 * badge de tipo + data + NPS), com estado vazio dedicado.
 */
@Component({
  selector: 'app-feedback-history-list',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './feedback-history-list.component.html',
  styleUrl: './feedback-history-list.component.css',
})
export class FeedbackHistoryListComponent {
  private readonly transloco = inject(TranslocoService);

  readonly items = input<Feedback[]>([]);
  readonly loading = input(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Trunca a mensagem para a prévia da lista — a íntegra não
   * tem outro lugar para ser vista neste módulo (sem endpoint `show`),
   * mas 140 caracteres já dão contexto suficiente na listagem.
   */
  protected preview(message: string): string {
    return message.length > PREVIEW_LENGTH ? `${message.slice(0, PREVIEW_LENGTH)}…` : message;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Classificação NPS do item (0–6 detrator, 7–8 neutro,
   * 9–10 promotor) — `null` quando o feedback não tem nota.
   */
  protected npsClass(score: number | null): 'det' | 'neu' | 'pro' | null {
    if (score === null) return null;
    if (score >= 9) return 'pro';
    if (score >= 7) return 'neu';
    return 'det';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Formata a data de criação no idioma ativo — método
   * simples (não `computed()`, já que não depende de nenhum Signal
   * próprio) reavaliado a cada ciclo de change detection, mesmo padrão
   * de locale (`INTL_LOCALE_BY_LANG`) já usado em outros módulos.
   */
  protected formatDate(isoDate: string): string {
    const locale = INTL_LOCALE_BY_LANG[this.transloco.getActiveLang()] ?? 'pt-BR';
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date(isoDate));
  }
}
