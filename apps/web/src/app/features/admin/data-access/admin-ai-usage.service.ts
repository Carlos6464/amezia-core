import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { AdminAiUsageOverviewResponse } from '@amezia/shared-types';

const BASE_URL = '/api/v1/admin/ai-usage';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Estado do overview de custo/uso de IA do Admin via Signals
 * (build-context-10 §3.3) — mesmo padrão de `AdminStatsService`.
 */
@Injectable({ providedIn: 'root' })
export class AdminAiUsageService {
  private readonly http = inject(HttpClient);

  readonly overview = signal<AdminAiUsageOverviewResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: GET /admin/ai-usage/overview — agregado do mês corrente
   * + top consumidores.
   */
  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.http.get<AdminAiUsageOverviewResponse>(`${BASE_URL}/overview`).subscribe({
      next: (overview) => {
        this.overview.set(overview);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('admin.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }
}
