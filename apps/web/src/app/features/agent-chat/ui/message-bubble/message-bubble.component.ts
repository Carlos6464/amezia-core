import { Component, computed, inject, input } from '@angular/core';
import { TranslocoService } from '@jsverse/transloco';

import { MarkdownPipe } from '../../../../shared/pipes/markdown.pipe';
import type { ConversationMessage } from '../../data-access/models';

const INTL_LOCALE_BY_LANG: Record<string, string> = { 'pt-BR': 'pt-BR', en: 'en-US' };

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-12
 * Descrição: Linha de mensagem "burra" (avatar + bolha) — layout
 * replicado do projeto irmão: bico assimétrico (`border-bottom-*-radius`
 * reduzido do lado de quem "fala"), avatar circular só nas mensagens do
 * assistente, alinhamento invertido (`row-reverse`) nas do usuário.
 * Mensagens do assistente passam por `MarkdownPipe` (negrito/itálico/
 * código/listas); mensagens do usuário são sempre texto puro. Data e
 * hora aparecem embaixo de cada bolha, como num app de conversa real
 * (pedido do usuário, 2026-08-12).
 */
@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [MarkdownPipe],
  templateUrl: './message-bubble.component.html',
  styleUrl: './message-bubble.component.css',
})
export class MessageBubbleComponent {
  private readonly transloco = inject(TranslocoService);

  readonly message = input.required<ConversationMessage>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Data + hora de `message().created_at` formatadas no
   * idioma ativo do Transloco (RN-10), mesmo padrão de locale já usado
   * em `TransactionFilterBarComponent.monthLabel` — `dateStyle`/
   * `timeStyle: 'short'` deixa o `Intl.DateTimeFormat` decidir a ordem
   * dia/mês/ano e o formato de hora (24h em pt-BR, 12h AM/PM em en) sem
   * precisar montar a string manualmente.
   */
  readonly formattedTimestamp = computed(() => {
    const locale = INTL_LOCALE_BY_LANG[this.transloco.getActiveLang()] ?? 'pt-BR';
    const createdAt = new Date(this.message().created_at);
    return new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeStyle: 'short' }).format(
      createdAt,
    );
  });
}
