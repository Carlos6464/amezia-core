import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { Feedback, FeedbackCreateRequest, FeedbackListResponse } from '@amezia/shared-types';
import { finalize } from 'rxjs';

const BASE_URL = '/api/v1/feedback';
const HISTORY_PAGE_SIZE = 50;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Estado da tela de Feedback via Signals (build-context-08
 * §3.2) — envio (aba "Enviar feedback") e histórico do próprio usuário
 * (aba "Histórico", carregado sob demanda na primeira troca de aba).
 */
@Injectable({ providedIn: 'root' })
export class FeedbackService {
  private readonly http = inject(HttpClient);

  readonly submitting = signal(false);
  readonly submitted = signal(false);
  readonly submitError = signal<string | null>(null);

  readonly history = signal<Feedback[]>([]);
  readonly historyTotal = signal(0);
  readonly loadingHistory = signal(false);
  readonly historyLoaded = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Envia o feedback do usuário autenticado (`POST
   * /feedback`, canal `web` forçado pelo backend) — atualiza
   * `submitting`/`submitted` e acrescenta o registro criado no início do
   * histórico local, já que ele nasce mais recente que qualquer outro.
   */
  submit(payload: FeedbackCreateRequest): void {
    this.submitting.set(true);
    this.submitError.set(null);
    this.http
      .post<Feedback>(BASE_URL, payload)
      .pipe(finalize(() => this.submitting.set(false)))
      .subscribe({
        next: (feedback) => {
          this.submitted.set(true);
          this.history.update((current) => [feedback, ...current]);
          this.historyTotal.update((total) => total + 1);
        },
        error: () => {
          this.submitError.set('feedback.errors.submitFailed');
        },
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Carrega o histórico paginado do usuário (`GET
   * /feedback/me`) — chamado pela página só na primeira vez que a aba
   * "Histórico" é aberta (`historyLoaded` evita recarregar à toa).
   */
  loadHistory(): void {
    this.loadingHistory.set(true);
    this.http
      .get<FeedbackListResponse>(BASE_URL + '/me', {
        params: { page: 1, page_size: HISTORY_PAGE_SIZE },
      })
      .pipe(finalize(() => this.loadingHistory.set(false)))
      .subscribe({
        next: (response) => {
          this.history.set(response.items);
          this.historyTotal.set(response.total);
          this.historyLoaded.set(true);
        },
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Volta o estado para "preenchendo" sem navegação — link
   * "Enviar outro feedback" do card de sucesso.
   */
  resetForm(): void {
    this.submitted.set(false);
    this.submitError.set(null);
  }
}
