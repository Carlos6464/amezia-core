import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { BudgetResponse, BudgetUpdateRequest } from '@amezia/shared-types';
import { Observable, tap } from 'rxjs';

const BASE_URL = '/api/v1/transactions/budget';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Teto mensal global do usuário (build-context-03 §2.9) —
 * consumido pelo card "Teto mensal" do stats-strip da listagem.
 */
@Injectable({ providedIn: 'root' })
export class BudgetService {
  private readonly http = inject(HttpClient);

  readonly monthlyBudget = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Carrega o teto mensal configurado (`null` se nunca
   * definido).
   */
  load(): void {
    this.http
      .get<BudgetResponse>(BASE_URL)
      .subscribe((response) => this.monthlyBudget.set(response.monthly_budget));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Define ou limpa (`value: null`) o teto mensal.
   */
  update(value: string | null): Observable<BudgetResponse> {
    const payload: BudgetUpdateRequest = { monthly_budget: value };
    return this.http
      .put<BudgetResponse>(BASE_URL, payload)
      .pipe(tap((response) => this.monthlyBudget.set(response.monthly_budget)));
  }
}
