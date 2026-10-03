import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { AdminPaginatedResponse, AdminUser, PaginationInfo, UserRole } from '@amezia/shared-types';
import { Observable, tap } from 'rxjs';

const BASE_URL = '/api/v1/admin/users';

const EMPTY_PAGINATION: PaginationInfo = { page: 1, page_size: 20, total: 0, total_pages: 0 };

export interface AdminUserFilters {
  search: string;
  role: UserRole | '';
  hasPhone: boolean | null;
  page: number;
  pageSize: number;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Filtros padrão da tela Usuários — sem busca, sem papel,
 * sem exigência de WhatsApp vinculado, página 1.
 */
export function defaultAdminUserFilters(): AdminUserFilters {
  return { search: '', role: '', hasPhone: null, page: 1, pageSize: 20 };
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Estado da listagem de usuários do Admin via Signals
 * (build-context-06 §3.3) — mesmo padrão de TransactionService
 * (paginação/filtro resolvidos pelo backend).
 */
@Injectable({ providedIn: 'root' })
export class AdminUsersService {
  private readonly http = inject(HttpClient);

  readonly users = signal<AdminUser[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly filters = signal<AdminUserFilters>(defaultAdminUserFilters());
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
    if (current.search) {
      params = params.set('search', current.search);
    }
    if (current.role) {
      params = params.set('role', current.role);
    }
    if (current.hasPhone !== null) {
      params = params.set('has_phone', String(current.hasPhone));
    }

    this.http.get<AdminPaginatedResponse<AdminUser>>(BASE_URL, { params }).subscribe({
      next: (response) => {
        this.users.set(response.items);
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
  updateFilters(partial: Partial<AdminUserFilters>): void {
    this.filters.update((current) => ({ ...current, ...partial, page: partial.page ?? 1 }));
    this.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: PATCH /admin/users/{id}/role — reflete o usuário
   * atualizado direto na listagem local, sem recarregar a página
   * inteira.
   */
  changeRole(userId: string, role: UserRole): Observable<AdminUser> {
    return this.http.patch<AdminUser>(`${BASE_URL}/${userId}/role`, { role }).pipe(
      tap((updated) => {
        this.users.update((list) => list.map((user) => (user.id === updated.id ? updated : user)));
      }),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: GET /admin/users/{id} — detalhe usado pelo modal de troca
   * de papel/futuras telas de detalhe.
   */
  getById(userId: string): Observable<AdminUser> {
    return this.http.get<AdminUser>(`${BASE_URL}/${userId}`);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: PATCH /admin/users/{id}/test-access — concede ou revoga
   * o acesso de teste Premium vitalício (sem Stripe, fora de qualquer
   * build-context). Mesmo padrão de `changeRole`: reflete o usuário
   * atualizado direto na listagem local.
   */
  setTestAccess(userId: string, enabled: boolean): Observable<AdminUser> {
    return this.http.patch<AdminUser>(`${BASE_URL}/${userId}/test-access`, { enabled }).pipe(
      tap((updated) => {
        this.users.update((list) => list.map((user) => (user.id === updated.id ? updated : user)));
      }),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: DELETE /admin/users/{id} — exclui permanentemente a
   * conta (fora de qualquer build-context, pedido direto do usuário
   * pra limpar contas de teste/debug criadas em produção). Remove o
   * usuário da listagem local e ajusta o total, sem recarregar a
   * página inteira.
   */
  deleteUser(userId: string): Observable<void> {
    return this.http.delete<void>(`${BASE_URL}/${userId}`).pipe(
      tap(() => {
        this.users.update((list) => list.filter((user) => user.id !== userId));
        this.pagination.update((current) => ({ ...current, total: Math.max(current.total - 1, 0) }));
      }),
    );
  }
}
