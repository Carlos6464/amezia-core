import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import type { BillingCycle, Plan } from '@amezia/shared-types';

import { ThemeService } from '../../../../core/theme/theme.service';
import { buildPlanFeatures } from '../../data-access/subscription.model';
import { SubscriptionService } from '../../data-access/subscription.service';
import { BillingCycleToggleComponent } from '../../ui/billing-cycle-toggle/billing-cycle-toggle.component';
import { PlanCardComponent } from '../../ui/plan-card/plan-card.component';
import type {
  PlanCardBadge,
  PlanCardCtaVariant,
  PlanCardFeature,
} from '../../ui/plan-card/plan-card.component';

interface PlanCardViewModel {
  plan: Plan;
  nameKey: string;
  badge: PlanCardBadge;
  taglineKey: string;
  priceCents: number;
  annualMonthlyEquivalentCents: number | null;
  features: PlanCardFeature[];
  ctaLabelKey: string;
  ctaVariant: PlanCardCtaVariant;
  highlighted: boolean;
}

const TAGLINE_BY_PLAN: Record<Plan, string> = {
  free: 'subscription.registerPlan.tagline.free',
  pro: 'subscription.registerPlan.tagline.pro',
  premium: 'subscription.registerPlan.tagline.premium',
};
const CTA_BY_PLAN: Record<Plan, string> = {
  free: 'subscription.registerPlan.cta.free',
  pro: 'subscription.registerPlan.cta.pro',
  premium: 'subscription.registerPlan.cta.premium',
};
const BADGE_BY_PLAN: Record<Plan, PlanCardBadge> = { free: 'free', pro: 'popular', premium: 'premium' };
const CTA_VARIANT_BY_PLAN: Record<Plan, PlanCardCtaVariant> = {
  free: 'free',
  pro: 'popular',
  premium: 'premium',
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Passo 1 de 3 do cadastro (build-context-09 §3.1/T17) —
 * escolha de plano antes do formulário de conta. Tela pública (sem
 * sessão nenhuma ainda), busca preço/limites reais via `GET
 * /subscriptions/plans` — nenhum valor hardcoded no template. Anual
 * fica travado em "em breve" (`BillingCycleToggleComponent`) enquanto
 * o Admin não cadastrar preço anual pra nenhum plano pago.
 */
@Component({
  selector: 'app-register-plan-page',
  standalone: true,
  imports: [TranslocoModule, RouterLink, PlanCardComponent, BillingCycleToggleComponent],
  templateUrl: './register-plan-page.component.html',
  styleUrl: './register-plan-page.component.css',
})
export class RegisterPlanPageComponent {
  private readonly subscriptionService = inject(SubscriptionService);
  private readonly router = inject(Router);
  protected readonly themeService = inject(ThemeService);

  protected readonly catalog = this.subscriptionService.catalog;
  protected readonly loading = this.subscriptionService.loadingCatalog;
  protected readonly billingCycle = signal<BillingCycle>('monthly');

  protected readonly annualAvailable = computed(() => {
    const catalog = this.catalog();
    return !!catalog && (catalog.pro.annual !== null || catalog.premium.annual !== null);
  });

  protected readonly planCards = computed<PlanCardViewModel[]>(() => {
    const catalog = this.catalog();
    if (!catalog) {
      return [];
    }
    const cycle = this.billingCycle();
    return (['free', 'pro', 'premium'] as const).map((plan) => {
      const entry = catalog[plan];
      const activePrice = cycle === 'annual' ? entry.annual : entry.monthly;
      const priceCents = activePrice?.unit_amount_cents ?? 0;
      const annualMonthlyEquivalentCents =
        cycle === 'annual' && entry.annual ? Math.round(entry.annual.unit_amount_cents / 12) : null;
      return {
        plan,
        nameKey: `subscription.planNames.${plan}`,
        badge: BADGE_BY_PLAN[plan],
        taglineKey: TAGLINE_BY_PLAN[plan],
        priceCents,
        annualMonthlyEquivalentCents,
        features: buildPlanFeatures(entry.limits),
        ctaLabelKey: CTA_BY_PLAN[plan],
        ctaVariant: CTA_VARIANT_BY_PLAN[plan],
        highlighted: plan === 'pro',
      };
    });
  });

  constructor() {
    this.subscriptionService.loadCatalog();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Navega pro formulário de conta (`/register`) já com o
   * plano/ciclo escolhidos na query string — `RegisterPageComponent`
   * lê esses parâmetros pra decidir se dispara o checkout do Stripe
   * depois do cadastro.
   */
  selectPlan(plan: Plan): void {
    if (plan === 'free') {
      this.router.navigate(['/register']);
      return;
    }
    this.router.navigate(['/register'], {
      queryParams: { plan, billing: this.billingCycle() },
    });
  }
}
