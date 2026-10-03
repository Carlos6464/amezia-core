import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { GetMyAiUsageResponse } from '@amezia/shared-types';

const BASE_URL = '/api/v1/ai-usage';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Estado de uso e limites de IA via Signals
 * (build-context-10 §3.2) — mesmo padrão de `AdminStatsService`
 * (dataset pequeno, sem paginação).
 */
@Injectable({ providedIn: 'root' })
export class AiUsageService {
  private readonly http = inject(HttpClient);

  readonly usage = signal<GetMyAiUsageResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Busca o uso do ciclo atual + histórico — chamado no
   * `ngOnInit` de `settings-usage-page`.
   */
  load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.http.get<GetMyAiUsageResponse>(`${BASE_URL}/me`).subscribe({
      next: (usage) => {
        this.usage.set(usage);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('aiUsage.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }
}
