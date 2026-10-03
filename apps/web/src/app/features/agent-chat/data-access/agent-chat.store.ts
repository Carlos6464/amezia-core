import { Injectable, inject, signal } from '@angular/core';
import { TranslocoService } from '@jsverse/transloco';
import { MessageService } from 'primeng/api';

import { AgentChatService } from './agent-chat.service';
import { AgentChatSocketService } from './agent-chat-socket.service';
import type { AiMessageReadyEvent, AiResponseFailedEvent, Conversation, ConversationMessage } from './models';

const MESSAGE_PAGE_SIZE = 50;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-12
 * Descrição: Estado do módulo Agente de IA via Signals — lista de
 * conversas (tela `/agent`), conversa/mensagens abertas (tela
 * `/agent/:publicId` ou `/agent/new`) e os 3 estados assíncronos de
 * envio (`sendingMessage`, `waitingResponse`, `providerError`).
 * Navegação por rota (layout replicado do projeto irmão, 2026-08-12) —
 * cada conversa é uma página própria, não um painel dentro de uma
 * tela só. Singleton (`providedIn: 'root'`): assina os streams do
 * WebSocket uma única vez no construtor, então eventos que chegam com
 * a tela em segundo plano não se perdem.
 */
@Injectable({ providedIn: 'root' })
export class AgentChatStore {
  private readonly agentChatService = inject(AgentChatService);
  private readonly socketService = inject(AgentChatSocketService);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);

  readonly conversations = signal<Conversation[]>([]);
  readonly activeConversation = signal<Conversation | null>(null);
  readonly messages = signal<ConversationMessage[]>([]);
  readonly loadingConversations = signal(false);
  readonly loadingMessages = signal(false);
  readonly sendingMessage = signal(false);
  readonly waitingResponse = signal<string | null>(null);
  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Erro pendente do chat — `reason` (2026-09-11) distingue
   * `'limit_reached'` (`event.error === 'ai.usageLimitExceeded'`,
   * publicado por `generate_ai_response` quando `CheckAiUsageLimitUseCase`
   * barra a chamada) de `'failed'` (provider indisponível ou erro de
   * rede no próprio `POST`) — antes os dois casos caíam na mesma
   * mensagem genérica de "tente novamente", enganosa quando o motivo
   * real é limite de plano (repetir não resolve até o próximo ciclo ou
   * um upgrade).
   */
  readonly providerError = signal<{
    conversationId: string;
    userMessageId: string;
    reason: 'limit_reached' | 'failed';
  } | null>(null);
  readonly deletingId = signal<string | null>(null);

  private lastSentContent: string | null = null;

  constructor() {
    this.socketService.messageReady$.subscribe((event) => this.onMessageReady(event));
    this.socketService.responseFailed$.subscribe((event) => this.onResponseFailed(event));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Carrega a listagem de conversas do usuário — chamado ao
   * abrir a tela de lista e sempre que uma resposta de IA muda
   * título/prévia de alguma conversa.
   */
  loadConversations(): void {
    this.loadingConversations.set(true);
    this.agentChatService.listConversations().subscribe({
      next: (result) => {
        this.conversations.set(result.items);
        this.loadingConversations.set(false);
      },
      error: () => this.loadingConversations.set(false),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Abre uma conversa existente pelo `publicId` da rota —
   * reaproveita a entrada já carregada em `conversations()` se houver
   * (navegação vinda da lista), e busca a listagem de qualquer forma
   * quando não há cache (reload/deep link direto em `/agent/:id`).
   */
  openConversationByPublicId(publicId: string): void {
    this.messages.set([]);
    this.providerError.set(null);
    this.loadingMessages.set(true);

    const cached = this.conversations().find((conversation) => conversation.public_id === publicId);
    this.activeConversation.set(cached ?? null);
    if (!cached) {
      this.agentChatService.listConversations().subscribe((result) => {
        this.conversations.set(result.items);
        const found = result.items.find((conversation) => conversation.public_id === publicId);
        if (found) {
          this.activeConversation.set(found);
        }
      });
    }

    this.agentChatService.listMessages(publicId, 1, MESSAGE_PAGE_SIZE).subscribe({
      next: (result) => {
        this.messages.set(result.items);
        this.loadingMessages.set(false);
      },
      error: () => this.loadingMessages.set(false),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Prepara o estado para `/agent/new` — nenhuma conversa
   * existe ainda no servidor; ela só é criada quando a primeira
   * mensagem é enviada (`sendMessage`).
   */
  startNewChat(): void {
    this.activeConversation.set(null);
    this.messages.set([]);
    this.providerError.set(null);
    this.loadingMessages.set(false);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Envia a mensagem do usuário. Sem conversa aberta ainda
   * (`/agent/new`), cria uma antes de enviar — quem chama (`ChatPage`)
   * observa `activeConversation()` para trocar a URL de `new` pelo
   * `public_id` real assim que ela existir. A resposta da IA nunca
   * vem no corpo do `POST`, só via WebSocket (`onMessageReady`); erro
   * de rede no próprio `POST` cai direto em `providerError` (mesmo
   * tratamento visual de `ai_response_failed`).
   */
  sendMessage(content: string): void {
    if (this.sendingMessage()) {
      return;
    }
    this.lastSentContent = content;
    this.sendingMessage.set(true);
    this.providerError.set(null);

    const conversation = this.activeConversation();
    if (conversation) {
      this.dispatchMessage(conversation.public_id, content);
      return;
    }

    this.agentChatService.createConversation().subscribe({
      next: (created) => {
        this.activeConversation.set(created);
        this.conversations.update((current) => [created, ...current]);
        this.dispatchMessage(created.public_id, content);
      },
      error: () => {
        this.sendingMessage.set(false);
        this.providerError.set({ conversationId: 'new', userMessageId: '', reason: 'failed' });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: `POST` efetivo da mensagem, já com uma conversa
   * garantida — acrescenta a bolha do usuário otimisticamente e entra
   * em `waiting_response`.
   */
  private dispatchMessage(conversationPublicId: string, content: string): void {
    this.agentChatService.sendMessage(conversationPublicId, content).subscribe({
      next: (accepted) => {
        this.messages.update((current) => [
          ...current,
          {
            public_id: accepted.message_id,
            role: 'user',
            content,
            provider_used: null,
            created_at: new Date().toISOString(),
          },
        ]);
        this.sendingMessage.set(false);
        this.waitingResponse.set(accepted.conversation_public_id);
      },
      error: () => {
        this.sendingMessage.set(false);
        this.providerError.set({ conversationId: conversationPublicId, userMessageId: '', reason: 'failed' });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Botão "Tentar novamente" do banner de erro — reenvia o
   * último conteúdo digitado pelo usuário para a mesma conversa.
   */
  retryLastMessage(): void {
    if (!this.lastSentContent) {
      return;
    }
    this.sendMessage(this.lastSentContent);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Exclui uma conversa da listagem (layout replicado do
   * projeto irmão — exclusão direta pelo botão do card, sem diálogo
   * de confirmação) e a retira do Signal local em caso de sucesso.
   * Toast de erro (build-context-13) — sem diálogo de confirmação, uma
   * falha muda deixava o card simplesmente parado de "excluindo" sem
   * nenhuma explicação; sucesso já é visível pelo próprio card sumir
   * da lista, sem precisar de toast.
   */
  removeConversation(publicId: string): void {
    if (this.deletingId() === publicId) {
      return;
    }
    this.deletingId.set(publicId);
    this.agentChatService.deleteConversation(publicId).subscribe({
      next: () => {
        this.conversations.update((current) =>
          current.filter((conversation) => conversation.public_id !== publicId),
        );
        this.deletingId.set(null);
      },
      error: () => {
        this.deletingId.set(null);
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('toasts.errorTitle'),
          detail: this.transloco.translate('toasts.agentChat.deleteError'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Handler do evento `ai_message_ready` — acrescenta a
   * resposta ao thread se a conversa afetada é a que está aberta, e
   * sempre recarrega a listagem (título automático/prévia/ordenação
   * podem ter mudado, mesmo em conversas fechadas). Depois de recarregar,
   * também atualiza `activeConversation` com a entrada fresca da lista
   * — sem isso, o título do header ficava preso em "Nova conversa"
   * mesmo depois do backend gerar o título automático na 1ª resposta
   * (bug real encontrado na validação em browser, 2026-08-12).
   */
  private onMessageReady(event: AiMessageReadyEvent): void {
    if (this.waitingResponse() === event.conversation_public_id) {
      this.waitingResponse.set(null);
    }
    const isActive = this.activeConversation()?.public_id === event.conversation_public_id;
    if (isActive) {
      this.messages.update((current) => [...current, event.message]);
    }

    this.agentChatService.listConversations().subscribe((result) => {
      this.conversations.set(result.items);
      if (isActive) {
        const refreshed = result.items.find(
          (conversation) => conversation.public_id === event.conversation_public_id,
        );
        if (refreshed) {
          this.activeConversation.set(refreshed);
        }
      }
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Handler do evento `ai_response_failed` — encerra a
   * espera e liga o banner de erro (build-context-04 §2.8). `error ===
   * 'ai.usageLimitExceeded'` (2026-09-11) vira `reason: 'limit_reached'`
   * em vez do genérico `'failed'` — ver docstring de `providerError`.
   */
  private onResponseFailed(event: AiResponseFailedEvent): void {
    if (this.waitingResponse() === event.conversation_public_id) {
      this.waitingResponse.set(null);
    }
    this.providerError.set({
      conversationId: event.conversation_public_id,
      userMessageId: event.user_message_id,
      reason: event.error === 'ai.usageLimitExceeded' ? 'limit_reached' : 'failed',
    });
  }
}
