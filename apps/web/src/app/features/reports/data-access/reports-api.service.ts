import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type {
  CategoryDistributionItem,
  DashboardCardPreference,
  DashboardLayoutResponse,
  FinancialSummary,
  MonthlyEvolutionPoint,
  MonthlyPaidPendingPoint,
  NarrativeQueuedResponse,
  NarrativeRequest,
  PaginatedTransactionsResponse,
  PaymentMethodDistributionItem,
} from '@amezia/shared-types';
import { Observable } from 'rxjs';

const BASE_URL = '/api/v1/reports';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Parâmetros comuns às queries de agregação (resumo,
 * distribuição, tabela) — intervalo de datas + filtro opcional de
 * categoria. Sem filtro de tipo: produto é expense-only (2026-08-14).
 */
export interface ReportsQueryParams {
  dateFrom: string;
  dateTo: string;
  categoryId?: string;
  paymentMethod?: string;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Cliente HTTP puro do módulo de Relatórios — sem estado
 * (Signals ficam em `ReportsStateService`). Um método por endpoint do
 * backend (build-context-05 §2.5).
 */
@Injectable({ providedIn: 'root' })
export class ReportsApiService {
  private readonly http = inject(HttpClient);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Monta os query params comuns (`date_from`/`date_to` +
   * `category_id` opcional) reaproveitados pela maioria dos endpoints
   * GET do módulo. `payment_method` (2026-09-15, fora de qualquer
   * build-context) só é enviado quando informado — hoje só o modal
   * "despesas por tipo de pagamento" do Dashboard passa esse campo,
   * chamando `getTransactions`.
   */
  private buildParams(params: ReportsQueryParams): HttpParams {
    let httpParams = new HttpParams().set('date_from', params.dateFrom).set('date_to', params.dateTo);
    if (params.categoryId) {
      httpParams = httpParams.set('category_id', params.categoryId);
    }
    if (params.paymentMethod) {
      httpParams = httpParams.set('payment_method', params.paymentMethod);
    }
    return httpParams;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: GET /reports/summary — resumo financeiro do período.
   */
  getSummary(params: ReportsQueryParams): Observable<FinancialSummary> {
    return this.http.get<FinancialSummary>(`${BASE_URL}/summary`, {
      params: this.buildParams(params),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: GET /reports/monthly-evolution — série mensal de
   * despesas, `months` meses corridos até `year`/`month`.
   */
  getMonthlyEvolution(year: number, month: number, months = 6): Observable<MonthlyEvolutionPoint[]> {
    const params = new HttpParams()
      .set('year', year)
      .set('month', month)
      .set('months', months);
    return this.http.get<MonthlyEvolutionPoint[]>(`${BASE_URL}/monthly-evolution`, { params });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: GET /reports/category-distribution — distribuição por
   * categoria do período, ordenada por total desc.
   */
  getCategoryDistribution(params: ReportsQueryParams): Observable<CategoryDistributionItem[]> {
    return this.http.get<CategoryDistributionItem[]>(`${BASE_URL}/category-distribution`, {
      params: this.buildParams(params),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: GET /reports/payment-method-distribution — distribuição
   * por tipo de pagamento do período, ordenada por total desc (pedido
   * direto do usuário, fora de qualquer build-context).
   */
  getPaymentMethodDistribution(params: ReportsQueryParams): Observable<PaymentMethodDistributionItem[]> {
    return this.http.get<PaymentMethodDistributionItem[]>(`${BASE_URL}/payment-method-distribution`, {
      params: this.buildParams(params),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: GET /reports/monthly-paid-pending — série mensal pago x
   * pendente, `months` meses corridos até `year`/`month` (pedido
   * direto do usuário, fora de qualquer build-context) — mesmo formato
   * de parâmetros de `getMonthlyEvolution`.
   */
  getMonthlyPaidPending(year: number, month: number, months = 6): Observable<MonthlyPaidPendingPoint[]> {
    const params = new HttpParams().set('year', year).set('month', month).set('months', months);
    return this.http.get<MonthlyPaidPendingPoint[]>(`${BASE_URL}/monthly-paid-pending`, { params });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: GET /reports/transactions — tabela paginada de
   * transações do intervalo.
   */
  getTransactions(
    params: ReportsQueryParams,
    page: number,
    pageSize: number,
  ): Observable<PaginatedTransactionsResponse> {
    const httpParams = this.buildParams(params).set('page', page).set('page_size', pageSize);
    return this.http.get<PaginatedTransactionsResponse>(`${BASE_URL}/transactions`, {
      params: httpParams,
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: GET /reports/export/csv — baixa o CSV como blob, com a
   * resposta completa (não só o corpo) para o chamador ler o nome do
   * arquivo em `Content-Disposition`.
   */
  exportCsv(params: ReportsQueryParams): Observable<HttpResponse<Blob>> {
    return this.http.get(`${BASE_URL}/export/csv`, {
      params: this.buildParams(params),
      responseType: 'blob',
      observe: 'response',
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: POST /reports/narrative — enfileira a geração da
   * narrativa; o texto chega depois via WebSocket
   * (`report.narrative.ready`/`report.narrative.failed`).
   */
  generateNarrative(payload: NarrativeRequest): Observable<NarrativeQueuedResponse> {
    return this.http.post<NarrativeQueuedResponse>(`${BASE_URL}/narrative`, payload);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: GET /reports/dashboard-layout — quais cards do
   * Dashboard o usuário personalizou (visibilidade + ordem), `null`
   * se nunca personalizou (pedido direto do usuário, fora de qualquer
   * build-context).
   */
  getDashboardLayout(): Observable<DashboardLayoutResponse> {
    return this.http.get<DashboardLayoutResponse>(`${BASE_URL}/dashboard-layout`);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: PUT /reports/dashboard-layout — salva o layout completo
   * (todos os 6 cards personalizáveis, visibilidade + ordem) de uma vez.
   */
  updateDashboardLayout(layout: DashboardCardPreference[]): Observable<DashboardLayoutResponse> {
    return this.http.put<DashboardLayoutResponse>(`${BASE_URL}/dashboard-layout`, { layout });
  }
}
