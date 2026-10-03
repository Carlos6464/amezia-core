import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type {
  BillingPortalResponse,
  CheckoutRequest,
  CheckoutResponse,
  GetMySubscriptionResponse,
  PlanCatalogResponse,
  PlanLimits,
  Subscription,
} from '@amezia/shared-types';
import { Observable, finalize, tap } from 'rxjs';

const BASE_URL = '/api/v1/subscriptions';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Estado de assinatura via Signals (build-context-09 §3.2)
 * — mesmo padrão de `FeedbackService` pras leituras (`loadCatalog`/
 * `loadMySubscription` populam Signals, sem o chamador se inscrever).
 * `checkout`/`openBillingPortal` fogem desse padrão de propósito: quem
 * chama precisa reagir ao resultado (redirecionar pro Stripe, ou só
 * atualizar a tela numa troca direta sem redirect) — um efeito
 * colateral só a página sabe decidir, então os dois devolvem o
 * Observable pra página se inscrever.
 */
@Injectable({ providedIn: 'root' })
export class SubscriptionService {
  private readonly http = inject(HttpClient);

  readonly catalog = signal<PlanCatalogResponse | null>(null);
  readonly loadingCatalog = signal(false);

  readonly mySubscription = signal<Subscription | null>(null);
  readonly myPlanLimits = signal<PlanLimits | null>(null);
  readonly loadingMySubscription = signal(false);

  readonly checkoutLoading = signal(false);
  readonly billingPortalLoading = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Catálogo público de planos (`GET /subscriptions/plans`,
   * sem JWT) — usado tanto por `register-plan-page` (antes do
   * cadastro existir) quanto por `settings-plans-page`.
   */
  loadCatalog(): void {
    this.loadingCatalog.set(true);
    this.http
      .get<PlanCatalogResponse>(`${BASE_URL}/plans`)
      .pipe(finalize(() => this.loadingCatalog.set(false)))
      .subscribe({ next: (catalog) => this.catalog.set(catalog) });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Assinatura do usuário autenticado (`GET
   * /subscriptions/me`) — usado por `settings-plans-page`.
   */
  loadMySubscription(): void {
    this.loadingMySubscription.set(true);
    this.http
      .get<GetMySubscriptionResponse>(`${BASE_URL}/me`)
      .pipe(finalize(() => this.loadingMySubscription.set(false)))
      .subscribe({
        next: (response) => {
          this.mySubscription.set(response.subscription);
          this.myPlanLimits.set(response.plan_limits);
        },
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: `POST /subscriptions/checkout` — cadastro com plano
   * pago ou upgrade/downgrade de plano já assinado. `checkout_url`
   * preenchido significa "redirecione pro Stripe"; `subscription`
   * preenchido significa "já trocou, sem redirect" (assinatura ativa
   * mudando de preço). Quem chama decide o que fazer com cada caso.
   */
  checkout(payload: CheckoutRequest): Observable<CheckoutResponse> {
    this.checkoutLoading.set(true);
    return this.http.post<CheckoutResponse>(`${BASE_URL}/checkout`, payload).pipe(
      tap((response) => {
        if (response.subscription) {
          this.mySubscription.set(response.subscription);
        }
      }),
      finalize(() => this.checkoutLoading.set(false)),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: `POST /subscriptions/billing-portal` — sessão do
   * Stripe Customer Portal (gerenciar cartão, cancelar, ver faturas).
   * Quem chama sempre redireciona pra `url` no sucesso.
   */
  openBillingPortal(): Observable<BillingPortalResponse> {
    this.billingPortalLoading.set(true);
    return this.http
      .post<BillingPortalResponse>(`${BASE_URL}/billing-portal`, {})
      .pipe(finalize(() => this.billingPortalLoading.set(false)));
  }
}
