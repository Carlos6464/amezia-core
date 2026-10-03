import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { AdminStats } from '@amezia/shared-types';

const BASE_URL = '/api/v1/admin/stats';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Estado dos KPIs da Visão Geral do Admin via Signals
 * (build-context-06 §3.3) — dataset pequeno, sem paginação/filtro.
 */
@Injectable({ providedIn: 'root' })
export class AdminStatsService {
  private readonly http = inject(HttpClient);

  readonly stats = signal<AdminStats | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Busca os KPIs globais — chamado no `ngOnInit` da
   * `admin-overview-page`.
   */
  load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.http.get<AdminStats>(BASE_URL).subscribe({
      next: (stats) => {
        this.stats.set(stats);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('admin.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }
}
