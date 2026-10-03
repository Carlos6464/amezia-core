import { Component, computed, effect, inject } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslocoService, TranslocoModule } from '@jsverse/transloco';

import { AgentChatStore } from '../../data-access/agent-chat.store';
import { MessageBubbleComponent } from '../../ui/message-bubble/message-bubble.component';
import { MessageInputComponent } from '../../ui/message-input/message-input.component';
import { TypingIndicatorComponent } from '../../ui/typing-indicator/typing-indicator.component';

const SUGGESTION_KEYS = [
  'agentChat.chat.suggestions.spentThisMonth',
  'agentChat.chat.suggestions.topCategory',
  'agentChat.chat.suggestions.withinBudget',
  'agentChat.chat.suggestions.compareLastMonths',
];

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-12
 * Descrição: Página `/agent/:publicId` (ou `/agent/new`) — chat de uma
 * conversa, layout replicado do projeto irmão (`agent-chat`): coluna
 * central de largura máxima, header com seta de voltar, estado de
 * boas-vindas com chips de sugestão, bolhas com bico assimétrico e
 * cápsula de input com textarea auto-ajustável.
 */
@Component({
  selector: 'app-chat-page',
  standalone: true,
  imports: [RouterLink, TranslocoModule, MessageBubbleComponent, MessageInputComponent, TypingIndicatorComponent],
  templateUrl: './chat-page.component.html',
  styleUrl: './chat-page.component.css',
})
export class ChatPageComponent {
  protected readonly store = inject(AgentChatStore);
  protected readonly suggestionKeys = SUGGESTION_KEYS;

  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);

  /** `true` quando a página foi montada em `/agent/new` — controla o redirecionamento pós-criação. */
  private readonly startedNew: boolean;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Título exibido no header — o da conversa aberta, ou o
   * rótulo padrão de conversa nova enquanto ela ainda não existe.
   */
  protected readonly title = computed(
    () => this.store.activeConversation()?.title ?? this.transloco.translate('agentChat.list.newConversation'),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: `true` quando a conversa aberta é a que está aguardando
   * a resposta assíncrona — controla o `typing-indicator` e desabilita
   * o input.
   */
  protected readonly isWaiting = computed(() => {
    const waiting = this.store.waitingResponse();
    return waiting !== null && waiting === this.store.activeConversation()?.public_id;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: `true` quando o erro de provider pendente pertence à
   * conversa aberta — ou, sem conversa ainda (`/agent/new`, criação
   * falhou), sempre que houver qualquer erro pendente. `providerError`
   * é sempre limpo em `openConversationByPublicId`/`startNewChat`, então
   * nunca sobrevive de uma página para outra.
   */
  protected readonly hasProviderError = computed(() => {
    const error = this.store.providerError();
    if (!error) {
      return false;
    }
    const conversation = this.store.activeConversation();
    return conversation ? error.conversationId === conversation.public_id : true;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Motivo do erro pendente da conversa aberta (`null`
   * quando `hasProviderError()` é `false`) — `'limit_reached'` esconde
   * o botão "Tentar novamente" (repetir não resolve até o próximo
   * ciclo/upgrade) e mostra um link "Ver planos" no lugar.
   */
  protected readonly providerErrorReason = computed(() => {
    if (!this.hasProviderError()) {
      return null;
    }
    return this.store.providerError()?.reason ?? null;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Lê o `publicId` da rota e resolve o estado inicial —
   * `/agent/new` começa sem conversa (`startNewChat`), `/agent/:id`
   * carrega a conversa existente. Um `effect()` observa
   * `activeConversation()`: assim que a primeira mensagem de uma
   * conversa nova cria o registro no servidor, troca a URL de `/new`
   * para `/agent/{id}` (`replaceUrl`, sem empilhar histórico) — mesmo
   * comportamento do projeto irmão.
   */
  constructor() {
    const publicId = this.route.snapshot.paramMap.get('publicId');
    this.startedNew = publicId === null;

    if (publicId) {
      this.store.openConversationByPublicId(publicId);
    } else {
      this.store.startNewChat();
    }

    effect(() => {
      const conversation = this.store.activeConversation();
      if (this.startedNew && conversation) {
        this.router.navigate(['/agent', conversation.public_id], { replaceUrl: true });
      }
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Envia uma sugestão clicada ou o texto digitado no
   * input — mesmo caminho do `AgentChatStore.sendMessage`.
   */
  send(content: string): void {
    this.store.sendMessage(content);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Traduz uma chave de sugestão para enviar como conteúdo
   * da mensagem — chamado a partir do `(click)` dos chips, onde um
   * pipe não pode ser usado diretamente (só em interpolação/binding de
   * propriedade, nunca em expressão de evento no Angular).
   */
  protected translateSuggestion(key: string): string {
    return this.transloco.translate(key);
  }
}
