import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import type {
  Conversation,
  ConversationListResponse,
  MessageAcceptedResponse,
  MessageListResponse,
} from './models';

const BASE_URL = '/api/v1/conversations';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-11
 * Descrição: Chamadas HTTP do módulo Agente de IA — espelha
 * `/api/v1/conversations/*` (build-context-04 §2.7). Não decide estado,
 * só traduz a API em Observables; `AgentChatStore` é quem orquestra.
 */
@Injectable({ providedIn: 'root' })
export class AgentChatService {
  private readonly http = inject(HttpClient);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: POST /conversations — cria uma conversa vazia
   * (`title=null`, `channel="web"`).
   */
  createConversation(): Observable<Conversation> {
    return this.http.post<Conversation>(BASE_URL, {});
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: GET /conversations — lista paginada, ordenada por
   * `last_message_at DESC NULLS LAST` (mais recente primeiro).
   */
  listConversations(page = 1, pageSize = 20): Observable<ConversationListResponse> {
    return this.http.get<ConversationListResponse>(BASE_URL, {
      params: { page, page_size: pageSize },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: GET /conversations/{publicId}/messages — histórico em
   * ordem cronológica.
   */
  listMessages(conversationPublicId: string, page = 1, pageSize = 50): Observable<MessageListResponse> {
    return this.http.get<MessageListResponse>(`${BASE_URL}/${conversationPublicId}/messages`, {
      params: { page, page_size: pageSize },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: POST /conversations/{publicId}/messages — persiste a
   * mensagem do usuário e enfileira a resposta; devolve `202` sem
   * conteúdo de resposta (chega depois via WebSocket).
   */
  sendMessage(conversationPublicId: string, content: string): Observable<MessageAcceptedResponse> {
    return this.http.post<MessageAcceptedResponse>(`${BASE_URL}/${conversationPublicId}/messages`, {
      content,
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: DELETE /conversations/{publicId} — exclui a conversa
   * (layout replicado do projeto irmão: botão de excluir no card da
   * lista, sem diálogo de confirmação).
   */
  deleteConversation(conversationPublicId: string): Observable<void> {
    return this.http.delete<void>(`${BASE_URL}/${conversationPublicId}`);
  }
}
