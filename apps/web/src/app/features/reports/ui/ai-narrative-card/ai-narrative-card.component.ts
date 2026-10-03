import { Component, DestroyRef, effect, inject, input, output, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { MarkdownPipe } from '../../../../shared/pipes/markdown.pipe';
import type { NarrativeState } from '../../data-access/reports.models';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Card de narrativa IA da tela de Reports (build-context-05
 * §3.4) — os 5 estados descritos na spec (vazio, loading, pronta, erro
 * de throttle, erro de provider) mais `limit_reached` (2026-09-11,
 * limite mensal do plano atingido — distinto de "erro de provider":
 * repetir não resolve, precisa esperar o ciclo ou fazer upgrade). O
 * texto renderizado vem do backend
 * com um subconjunto leve de markdown (`**negrito**`) — tratado como
 * conteúdo do usuário/IA, nunca `[innerHTML]` sem sanitização (mesmo
 * `MarkdownPipe` do Agente de IA, build-context-04, que escapa
 * entidades HTML antes de aplicar as substituições).
 */
@Component({
  selector: 'app-ai-narrative-card',
  standalone: true,
  imports: [TranslocoModule, MarkdownPipe, RouterLink],
  templateUrl: './ai-narrative-card.component.html',
  styleUrl: './ai-narrative-card.component.css',
})
export class AiNarrativeCardComponent {
  private readonly destroyRef = inject(DestroyRef);

  state = input.required<NarrativeState>();
  narrative = input<string | null>(null);
  periodLabel = input.required<string>();
  retryAfterSeconds = input(10);

  generate = output<void>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `true` enquanto o botão "Gerar análise" fica desabilitado
   * após um `429` — reabilita sozinho depois de `retryAfterSeconds`
   * (spec §3.4: "não deve travar o botão indefinidamente"). Só controla
   * a UI; o limite de verdade é sempre reforçado pelo backend.
   */
  protected readonly retryBlocked = signal(false);
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    effect(() => {
      if (this.state() === 'throttled') {
        this.retryBlocked.set(true);
        this.clearTimer();
        this.timer = setTimeout(() => this.retryBlocked.set(false), this.retryAfterSeconds() * 1000);
      } else {
        this.retryBlocked.set(false);
        this.clearTimer();
      }
    });
    this.destroyRef.onDestroy(() => this.clearTimer());
  }

  private clearTimer(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}
