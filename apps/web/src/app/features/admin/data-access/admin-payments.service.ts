import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { AdminPaymentsResponse } from '@amezia/shared-types';

const BASE_URL = '/api/v1/admin/payments';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-11
 * Descrição: Estado da tela de Pagamentos via Signals (build-context-11
 * §3.2) — KPIs financeiros + feeds, tudo numa única chamada.
 */
@Injectable({ providedIn: 'root' })
export class AdminPaymentsService {
  private readonly http = inject(HttpClient);

  readonly payments = signal<AdminPaymentsResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: GET /admin/payments — chamado no `ngOnInit` da
   * `admin-payments-page`.
   */
  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.http.get<AdminPaymentsResponse>(BASE_URL).subscribe({
      next: (response) => {
        this.payments.set(response);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('admin.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }
}
