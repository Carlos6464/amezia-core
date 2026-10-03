import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type {
  BulkDeleteRequest,
  BulkDeleteResponse,
  PaginationInfo,
  Transaction,
  TransactionCreateRequest,
  TransactionListResponse,
  TransactionSummary,
  TransactionUpdateRequest,
} from '@amezia/shared-types';
import { Observable, tap } from 'rxjs';

import { defaultTransactionFilters, type TransactionFilters } from './transaction-filters.model';

const BASE_URL = '/api/v1/transactions';

const EMPTY_PAGINATION: PaginationInfo = { page: 1, page_size: 10, total: 0, total_pages: 0 };
const EMPTY_SUMMARY: TransactionSummary = {
  total_amount: '0.00',
  count: 0,
  budget_limit: null,
  budget_used_percentage: null,
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Estado da listagem de transações via Signals — diferente do
 * módulo Categorias, aqui a paginação/soma/busca já vêm prontas do
 * backend (dataset "ilimitado" por usuário, não cabe filtrar em memória
 * no cliente).
 */
@Injectable({ providedIn: 'root' })
export class TransactionService {
  private readonly http = inject(HttpClient);

  readonly transactions = signal<Transaction[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly filters = signal<TransactionFilters>(defaultTransactionFilters());
  readonly pagination = signal<PaginationInfo>(EMPTY_PAGINATION);
  readonly summary = signal<TransactionSummary>(EMPTY_SUMMARY);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Busca a página atual conforme `filters()` — chamado no
   * `ngOnInit`/`effect` da página e sempre que os filtros mudam.
   */
  load(): void {
    this.loading.set(true);
    this.error.set(null);
    const current = this.filters();

    let params = new HttpParams()
      .set('year', current.year)
      .set('month', current.month)
      .set('page', current.page)
      .set('page_size', current.pageSize);
    if (current.status) {
      params = params.set('status', current.status);
    }
    if (current.q) {
      params = params.set('q', current.q);
    }

    this.http.get<TransactionListResponse>(BASE_URL, { params }).subscribe({
      next: (response) => {
        this.transactions.set(response.items);
        this.pagination.set(response.pagination);
        this.summary.set(response.summary);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('transactions.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Mescla os filtros informados nos atuais e recarrega —
   * qualquer mudança de filtro (exceto paginação explícita) volta para
   * a página 1.
   */
  updateFilters(partial: Partial<TransactionFilters>): void {
    this.filters.update((current) => ({ ...current, ...partial, page: partial.page ?? 1 }));
    this.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Volta os filtros ao padrão (mês corrente, sem busca) —
   * botão "Limpar" da filter-bar.
   */
  resetFilters(): void {
    this.filters.set(defaultTransactionFilters());
    this.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Navega para outra página mantendo os demais filtros —
   * usado pelo rodapé de paginação.
   */
  goToPage(page: number): void {
    this.filters.update((current) => ({ ...current, page }));
    this.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Cria uma transação (simples, parcelada ou recorrente
   * conforme o payload) — não atualiza o Signal local sozinho, porque a
   * lista pode ganhar várias linhas de uma vez (parcelamento); quem
   * chama decide se recarrega via `load()`.
   */
  create(payload: TransactionCreateRequest): Observable<Transaction> {
    return this.http.post<Transaction>(BASE_URL, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Busca o detalhe de uma transação — usado no
   * pré-preenchimento do formulário de edição.
   */
  get(publicId: string): Observable<Transaction> {
    return this.http.get<Transaction>(`${BASE_URL}/${publicId}`);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Atualiza uma transação existente.
   */
  update(publicId: string, payload: TransactionUpdateRequest): Observable<Transaction> {
    return this.http.put<Transaction>(`${BASE_URL}/${publicId}`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Exclui uma transação e recarrega a página atual via
   * `load()` — não basta tirar a linha do Signal `transactions` local
   * (bug real: os cards de resumo no topo, `summary.total_amount`/
   * `count`, e a paginação ficavam com o valor de antes da exclusão,
   * porque só vêm prontos do backend, não são recalculados no
   * cliente). `options.allOccurrences` (transação recorrente, "excluir
   * todas") passa `all_occurrences=true` pro backend, que aí apaga todo
   * o histórico da recorrência de uma vez — mais um motivo pra sempre
   * recarregar em vez de tentar adivinhar em memória quais linhas
   * mudaram.
   */
  remove(publicId: string, options?: { allOccurrences?: boolean }): Observable<void> {
    const params = options?.allOccurrences ? new HttpParams().set('all_occurrences', 'true') : undefined;
    return this.http.delete<void>(`${BASE_URL}/${publicId}`, { params }).pipe(tap(() => this.load()));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Exclusão em lote (ex.: todas as parcelas de uma compra) —
   * idempotente no backend, ids que não existem são ignorados. Recarrega
   * a página atual via `load()` em vez de só filtrar o Signal local
   * (mesmo motivo de `remove()`: `summary`/paginação não se recalculam
   * sozinhos no cliente).
   */
  bulkRemove(publicIds: string[]): Observable<BulkDeleteResponse> {
    const payload: BulkDeleteRequest = { public_ids: publicIds };
    return this.http
      .post<BulkDeleteResponse>(`${BASE_URL}/bulk-delete`, payload)
      .pipe(tap(() => this.load()));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Upload de comprovante (multipart) — só funciona para uma
   * transação já existente (`public_id` obrigatório no backend).
   */
  uploadReceipt(publicId: string, file: File): Observable<Transaction> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<Transaction>(`${BASE_URL}/${publicId}/receipt`, formData);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Remove o comprovante anexado a uma transação.
   */
  deleteReceipt(publicId: string): Observable<Transaction> {
    return this.http.delete<Transaction>(`${BASE_URL}/${publicId}/receipt`);
  }
}
