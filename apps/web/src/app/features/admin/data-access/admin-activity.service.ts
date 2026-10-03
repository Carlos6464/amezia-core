import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { AdminActivityListResponse } from '@amezia/shared-types';

const BASE_URL = '/api/v1/admin/activity';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-11
 * Descrição: Estado do feed "Atividade recente" via Signals
 * (build-context-11 §3.1) — reaproveitado pela Visão Geral (últimos
 * itens) e por uma futura tela dedicada, se vier a existir.
 */
@Injectable({ providedIn: 'root' })
export class AdminActivityService {
  private readonly http = inject(HttpClient);

  readonly activity = signal<AdminActivityListResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: GET /admin/activity — busca uma página do feed.
   */
  load(page = 1, pageSize = 20): void {
    this.loading.set(true);
    this.error.set(null);
    this.http
      .get<AdminActivityListResponse>(BASE_URL, { params: { page, page_size: pageSize } })
      .subscribe({
        next: (response) => {
          this.activity.set(response);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('admin.errors.loadFailed');
          this.loading.set(false);
        },
      });
  }
}
