import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import type { AdminPlanPrice, BillingCycle, PaidPlan } from '@amezia/shared-types';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { PlanPricesService } from '../../data-access/plan-prices.service';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Tela de listagem de preços dos planos no Admin —
 * `GET /admin/plan-prices` (reformulação de 2026-09-10, catálogo
 * editável via API em vez dos 4 `STRIPE_PRICE_*` fixos no `.env`).
 * Cadastro/edição de preço fica numa tela separada
 * (`admin-plan-price-form-page`, a pedido do usuário — listar e
 * cadastrar são responsabilidades diferentes). Sem edição de limites
 * por plano (`PlanLimits`) nem de trial/cupons: nenhum dos dois tem
 * endpoint de escrita no backend ainda (protótipo `screem/admin-plans`
 * mostrava ambos, mas não fazem parte do escopo implementado do
 * build-context-09 — sinalizado ao usuário na resposta desta task).
 * Sem campo de "categorias privadas": decisão de escopo #1 do
 * build-context-09, sem limite de categoria em nenhum plano.
 */
@Component({
  selector: 'app-admin-plans-page',
  standalone: true,
  imports: [RouterLink, TranslocoModule, BrlAmountPipe, DatePipe],
  templateUrl: './admin-plans-page.component.html',
  styleUrl: './admin-plans-page.component.css',
})
export class AdminPlansPageComponent implements OnInit {
  private readonly planPricesService = inject(PlanPricesService);

  readonly loading = this.planPricesService.loading;
  readonly error = this.planPricesService.error;

  protected readonly plans: PaidPlan[] = ['pro', 'premium'];

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Preço ativo atual de cada (plano, ciclo) — usado nos 2
   * cards de resumo no topo da página. `undefined` quando o plano ainda
   * não tem nenhum preço cadastrado naquele ciclo.
   */
  protected readonly activePrice = computed(() => {
    const catalog = this.planPricesService.catalog();
    const lookup = (plan: PaidPlan, cycle: BillingCycle): AdminPlanPrice | undefined =>
      catalog[plan].find((price) => price.billing_cycle === cycle && price.active);
    return {
      pro: { monthly: lookup('pro', 'monthly'), annual: lookup('pro', 'annual') },
      premium: { monthly: lookup('premium', 'monthly'), annual: lookup('premium', 'annual') },
    };
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Histórico completo (Pro + Premium, ativos e arquivados)
   * ordenado do mais recente pro mais antigo — alimenta a tabela de
   * listagem abaixo dos cards de resumo.
   */
  protected readonly history = computed(() => {
    const catalog = this.planPricesService.catalog();
    return [...catalog.pro, ...catalog.premium].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Carrega o catálogo de preços ao montar a página — também
   * recarregado ao voltar da tela de cadastro (a navegação por rota
   * remonta este componente, sem precisar de evento manual).
   */
  ngOnInit(): void {
    this.planPricesService.load();
  }
}
