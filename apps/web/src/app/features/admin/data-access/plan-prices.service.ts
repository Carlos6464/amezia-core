import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { AdminPlanPrice, AdminPlanPricesCatalogResponse, CreatePlanPriceRequest, PaidPlan } from '@amezia/shared-types';
import { Observable, tap } from 'rxjs';

const BASE_URL = '/api/v1/admin/plan-prices';

const EMPTY_CATALOG: AdminPlanPricesCatalogResponse = { pro: [], premium: [] };

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Estado do catálogo de preços (Pro/Premium) via Signals,
 * consumido pela tela de gestão de planos do Admin — reformulação de
 * 2026-09-10 que trocou os 4 `STRIPE_PRICE_*` fixos no `.env` por um
 * catálogo editável via API (Product/Price do Stripe criados sob
 * demanda, nunca mais pelo dashboard manualmente).
 */
@Injectable({ providedIn: 'root' })
export class PlanPricesService {
  private readonly http = inject(HttpClient);

  readonly catalog = signal<AdminPlanPricesCatalogResponse>(EMPTY_CATALOG);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: GET /admin/plan-prices — histórico completo (ativos e
   * arquivados) dos preços de Pro/Premium.
   */
  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.http.get<AdminPlanPricesCatalogResponse>(BASE_URL).subscribe({
      next: (response) => {
        this.catalog.set(response);
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
   * Data: 2026-09-10
   * Descrição: POST /admin/plan-prices/{plan} — cria um Price novo pro
   * (plano, ciclo) informado e arquiva o anterior da mesma combinação
   * (Price do Stripe é imutável em valor, nunca uma edição in-place).
   * Recarrega o catálogo inteiro após criar, pra refletir o novo preço
   * ativo e o antigo arquivado numa só chamada.
   */
  createOrUpdate(plan: PaidPlan, payload: CreatePlanPriceRequest): Observable<AdminPlanPrice> {
    return this.http
      .post<AdminPlanPrice>(`${BASE_URL}/${plan}`, payload)
      .pipe(tap(() => this.load()));
  }
}
