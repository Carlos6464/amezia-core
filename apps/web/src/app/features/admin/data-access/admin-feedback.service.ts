import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { AdminFeedback, AdminPaginatedResponse, FeedbackChannel, PaginationInfo } from '@amezia/shared-types';

const BASE_URL = '/api/v1/admin/feedback';

const EMPTY_PAGINATION: PaginationInfo = { page: 1, page_size: 20, total: 0, total_pages: 0 };

export interface AdminFeedbackFilters {
  channel: FeedbackChannel | '';
  search: string;
  page: number;
  pageSize: number;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Filtros padrão da tela Feedback — sem canal, sem busca,
 * página 1.
 */
export function defaultAdminFeedbackFilters(): AdminFeedbackFilters {
  return { channel: '', search: '', page: 1, pageSize: 20 };
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Estado da listagem de feedbacks do Admin via Signals
 * (build-context-06 §3.3/§2.9) — reaproveita o mesmo `pagination/`
 * genérico da tela Usuários.
 */
@Injectable({ providedIn: 'root' })
export class AdminFeedbackService {
  private readonly http = inject(HttpClient);

  readonly feedback = signal<AdminFeedback[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly filters = signal<AdminFeedbackFilters>(defaultAdminFeedbackFilters());
  readonly pagination = signal<PaginationInfo>(EMPTY_PAGINATION);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Busca a página atual conforme `filters()`.
   */
  load(): void {
    this.loading.set(true);
    this.error.set(null);
    const current = this.filters();

    let params = new HttpParams().set('page', current.page).set('page_size', current.pageSize);
    if (current.channel) {
      params = params.set('channel', current.channel);
    }
    if (current.search) {
      params = params.set('search', current.search);
    }

    this.http.get<AdminPaginatedResponse<AdminFeedback>>(BASE_URL, { params }).subscribe({
      next: (response) => {
        this.feedback.set(response.items);
        this.pagination.set({
          page: response.page,
          page_size: response.page_size,
          total: response.total,
          total_pages: response.total_pages,
        });
        this.loading.set(false);
      },
      error: () => {
        this.error.set('admin.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Mescla os filtros informados nos atuais e recarrega —
   * qualquer mudança de filtro (exceto paginação explícita) volta para
   * a página 1.
   */
  updateFilters(partial: Partial<AdminFeedbackFilters>): void {
    this.filters.update((current) => ({ ...current, ...partial, page: partial.page ?? 1 }));
    this.load();
  }
}
