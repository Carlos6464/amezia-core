import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { TranslocoService, TranslocoModule } from '@jsverse/transloco';

import { AgentChatStore } from '../../data-access/agent-chat.store';
import type { Conversation } from '../../data-access/models';

const INTL_LOCALES: Record<string, string> = { 'pt-BR': 'pt-BR', en: 'en-US' };

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-12
 * Descrição: Página `/agent` — grid de cards de conversa, layout
 * replicado do projeto irmão (`agent-list`). Cada card navega para
 * `/agent/:publicId`; "+ Nova conversa" navega para `/agent/new`
 * (nenhuma conversa é criada até a primeira mensagem ser enviada lá).
 */
@Component({
  selector: 'app-conversation-list-page',
  standalone: true,
  imports: [RouterLink, TranslocoModule],
  templateUrl: './conversation-list-page.component.html',
  styleUrl: './conversation-list-page.component.css',
})
export class ConversationListPageComponent {
  protected readonly store = inject(AgentChatStore);
  protected readonly skeletonPlaceholders = [1, 2, 3, 4, 5, 6];

  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Dispara o carregamento da listagem ao montar a página —
   * equivalente ao `ngOnInit()`.
   */
  constructor() {
    this.store.loadConversations();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Abre o chat da conversa selecionada.
   */
  open(conversation: Conversation): void {
    this.router.navigate(['/agent', conversation.public_id]);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Exclui a conversa sem navegar — `stopPropagation` evita
   * que o clique no botão de excluir (dentro do card-botão) também
   * dispare a abertura do chat.
   */
  remove(conversation: Conversation, event: MouseEvent): void {
    event.stopPropagation();
    this.store.removeConversation(conversation.public_id);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Formata `last_message_at`/`created_at` como "dia mês,
   * hora:min" no idioma ativo do perfil (RN-10) — mesmo padrão do
   * projeto irmão, só que sem fixar `pt-BR` (o nome do mês muda por
   * idioma).
   */
  formatDate(iso: string): string {
    const locale = INTL_LOCALES[this.transloco.getActiveLang()] ?? 'pt-BR';
    return new Intl.DateTimeFormat(locale, {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso));
  }
}
