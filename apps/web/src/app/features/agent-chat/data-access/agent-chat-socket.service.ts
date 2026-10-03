import { Injectable, inject } from '@angular/core';
import { Observable, filter, map } from 'rxjs';

import { WebSocketService } from '../../../core/websocket/websocket.service';
import type { AiMessageReadyEvent, AiResponseFailedEvent } from './models';

interface WsEnvelope {
  event?: string;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-11
 * Descrição: Não abre uma conexão WebSocket própria — injeta o
 * `WebSocketService` singleton de `core/websocket/` (já conectado desde
 * o login, build-context-01) e filtra o stream `messages$` pelos
 * eventos `ai_message_ready`/`ai_response_failed` (build-context-04
 * §2.8). `AgentChatStore` assina esses streams para atualizar o estado.
 */
@Injectable({ providedIn: 'root' })
export class AgentChatSocketService {
  private readonly webSocketService = inject(WebSocketService);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Sub-stream de `messages$` filtrado só pelo evento
   * `ai_message_ready` (resposta da IA gerada com sucesso) — quem
   * assina não precisa checar `event` manualmente.
   */
  readonly messageReady$: Observable<AiMessageReadyEvent> = this.webSocketService.messages$.pipe(
    filter((message): message is WsEnvelope => (message as WsEnvelope)?.event === 'ai_message_ready'),
    map((message) => message as AiMessageReadyEvent),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Sub-stream de `messages$` filtrado só pelo evento
   * `ai_response_failed` (Gemini e Grok falharam para a mensagem) —
   * `AgentChatStore` assina para acionar o banner de erro.
   */
  readonly responseFailed$: Observable<AiResponseFailedEvent> = this.webSocketService.messages$.pipe(
    filter(
      (message): message is WsEnvelope => (message as WsEnvelope)?.event === 'ai_response_failed',
    ),
    map((message) => message as AiResponseFailedEvent),
  );
}
