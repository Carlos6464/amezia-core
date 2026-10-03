import { HttpClient, HttpContext, HttpHeaders, HttpParams, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Category, CategoryDistributionItem, FinancialSummary, PaginatedTransactionsResponse } from '@amezia/shared-types';
import { Observable } from 'rxjs';

import { SKIP_AUTH_INTERCEPTOR } from '../../../../core/http/skip-auth-interceptor.token';

const REPORTS_URL = '/api/v1/reports';
const CATEGORIES_URL = '/api/v1/categories';

export interface SharedReportParams {
  dateFrom: string;
  dateTo: string;
  categoryId?: string;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-18
 * Descrição: Cliente HTTP dedicado da tela de Relatórios compartilhada
 * (`/reports/shared?token=...`, link mágico do bot do WhatsApp) —
 * deliberadamente **não** é o `ReportsApiService` do app: essa tela
 * roda fora do sistema autenticado (pedido explícito do usuário, depois
 * de uma 1ª tentativa que reaproveitava o `ReportsPageComponent`/
 * `ReportsStateService`/`AuthService` reais ter sido rejeitada — mesmo
 * sem nenhum link de volta visível, tecnicamente ainda era "o mesmo
 * código do sistema"). Cada método recebe o `token` explicitamente e
 * monta o header `Authorization` na mão, com `SKIP_AUTH_INTERCEPTOR`
 * pra `jwtInterceptor` nem tocar na requisição — zero dependência de
 * `AuthService`/`ReportsStateService`/`CategoriesService`.
 */
@Injectable({ providedIn: 'root' })
export class SharedReportApiService {
  private readonly http = inject(HttpClient);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Headers + context comuns a toda chamada desta tela — o
   * token do link (não o do `AuthService`) e a marcação pra pular o
   * interceptor global.
   */
  private options(token: string, params?: Record<string, string>) {
    return {
      headers: new HttpHeaders({ Authorization: `Bearer ${token}` }),
      context: new HttpContext().set(SKIP_AUTH_INTERCEPTOR, true),
      params: params ? new HttpParams({ fromObject: params }) : undefined,
    };
  }

  private queryParams(params: SharedReportParams): Record<string, string> {
    const query: Record<string, string> = { date_from: params.dateFrom, date_to: params.dateTo };
    if (params.categoryId) {
      query['category_id'] = params.categoryId;
    }
    return query;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: GET /reports/summary com o token do link — resumo
   * financeiro do intervalo, mesmo formato que `ReportsApiService`
   * expõe pro app logado.
   */
  getSummary(token: string, params: SharedReportParams): Observable<FinancialSummary> {
    return this.http.get<FinancialSummary>(
      `${REPORTS_URL}/summary`,
      this.options(token, this.queryParams(params)),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: GET /reports/category-distribution com o token do link
   * — ranking de categorias do intervalo, ordenado por total desc.
   */
  getCategoryDistribution(token: string, params: SharedReportParams): Observable<CategoryDistributionItem[]> {
    return this.http.get<CategoryDistributionItem[]>(
      `${REPORTS_URL}/category-distribution`,
      this.options(token, this.queryParams(params)),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: GET /reports/transactions com o token do link — tabela
   * paginada de transações do intervalo/filtro atuais.
   */
  getTransactions(
    token: string,
    params: SharedReportParams,
    page: number,
    pageSize: number,
  ): Observable<PaginatedTransactionsResponse> {
    const query = { ...this.queryParams(params), page: String(page), page_size: String(pageSize) };
    return this.http.get<PaginatedTransactionsResponse>(`${REPORTS_URL}/transactions`, this.options(token, query));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Lista de categorias pro dropdown de filtro — mesmo
   * `GET /categories` do app, mas chamado direto aqui (não via
   * `CategoriesService`, que é o serviço "do sistema" e traria consigo
   * a mesma dependência que essa tela precisa evitar).
   */
  listCategories(token: string): Observable<Category[]> {
    return this.http.get<Category[]>(CATEGORIES_URL, this.options(token));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: GET /reports/export/csv com o token do link — baixa o
   * CSV do filtro atual como blob, resposta completa (não só o corpo)
   * pra `SharedReportPageComponent` ler o nome do arquivo em
   * `Content-Disposition`.
   */
  exportCsv(token: string, params: SharedReportParams): Observable<HttpResponse<Blob>> {
    return this.http.get(`${REPORTS_URL}/export/csv`, {
      ...this.options(token, this.queryParams(params)),
      responseType: 'blob',
      observe: 'response',
    });
  }
}
