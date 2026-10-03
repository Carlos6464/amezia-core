import { Component, OnInit, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import type { Plan } from '@amezia/shared-types';

import { AuthService } from '../../../../core/auth/auth.service';
import { PLAN_ORDER, buildPlanFeatures } from '../../../subscription/data-access/subscription.model';
import { SubscriptionService } from '../../../subscription/data-access/subscription.service';
import { PlanCardComponent } from '../../../subscription/ui/plan-card/plan-card.component';
import type { PlanCardBadge, PlanCardFeature } from '../../../subscription/ui/plan-card/plan-card.component';
import { AiUsageService } from '../../data-access/ai-usage.service';
import { UsageHistoryTableComponent } from '../../ui/usage-history-table/usage-history-table.component';
import { UsageProgressBarComponent } from '../../ui/usage-progress-bar/usage-progress-bar.component';

interface UsagePlanCardViewModel {
  plan: Plan;
  nameKey: string;
  badge: PlanCardBadge;
  taglineKey: string;
  priceCents: number;
  features: PlanCardFeature[];
  isCurrent: boolean;
}

const TAGLINE_BY_PLAN: Record<Plan, string> = {
  free: 'subscription.registerPlan.tagline.free',
  pro: 'subscription.registerPlan.tagline.pro',
  premium: 'subscription.registerPlan.tagline.premium',
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Nova aba "Uso e Limites" em Configurações (build-context-10
 * §3.1) — banner do plano atual, alerta quando uso >= 80% do limite,
 * barras de progresso (conversas/relatórios de IA vêm daqui; Bot
 * WhatsApp/CSV vêm de `PlanLimits`+`Subscription`, já carregados por
 * `SubscriptionService`, sem endpoint próprio — fonte de dado diferente
 * da mesma tela, conforme a spec), histórico mensal e comparativo de
 * planos reaproveitando `ui/plan-card` (build-context-09), sem duplicar
 * a lógica de checkout — o CTA de cada card leva pra `/settings/plans`,
 * onde a troca de plano de fato acontece.
 */
@Component({
  selector: 'app-settings-usage-page',
  standalone: true,
  imports: [
    TranslocoModule,
    RouterLink,
    UsageProgressBarComponent,
    UsageHistoryTableComponent,
    PlanCardComponent,
  ],
  templateUrl: './settings-usage-page.component.html',
  styleUrl: './settings-usage-page.component.css',
})
export class SettingsUsagePageComponent implements OnInit {
  private readonly aiUsageService = inject(AiUsageService);
  private readonly subscriptionService = inject(SubscriptionService);
  private readonly authService = inject(AuthService);

  protected readonly usage = this.aiUsageService.usage;
  protected readonly loading = this.aiUsageService.loading;
  protected readonly subscription = this.subscriptionService.mySubscription;
  protected readonly planLimits = this.subscriptionService.myPlanLimits;
  protected readonly catalog = this.subscriptionService.catalog;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: `true` em acesso de teste Premium vitalício concedido
   * pelo admin — esconde o banner "Gerenciar assinatura" e o
   * comparativo de planos (mesmo motivo de `AppShellComponent.
   * isAdminTestAccess`): sem assinatura real por trás, não faz
   * sentido oferecer checkout/portal de cobrança.
   */
  protected readonly isAdminTestAccess = computed(
    () => this.subscription()?.is_admin_test_access ?? false,
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: `true` também pra papel `admin` — mesmo motivo de
   * `AppShellComponent.hidePlanArea` (pedido do usuário: um admin
   * navegando no app do cliente comum não pode ver a área de plano).
   */
  protected readonly hidePlanArea = computed(
    () => this.isAdminTestAccess() || this.authService.currentUser()?.role === 'admin',
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: `true` quando qualquer uma das 4 métricas já bateu 80%
   * do limite do plano — controla o alerta âmbar com CTA "Ver planos"
   * (build-context-10 §3.1).
   */
  protected readonly showUpgradeAlert = computed(() => {
    const usage = this.usage();
    if (!usage) {
      return false;
    }
    const nearLimit = (used: number, limit: number | null) =>
      limit !== null && limit > 0 && used / limit >= 0.8;

    return (
      nearLimit(usage.ai_conversations_used, usage.ai_conversations_limit) ||
      nearLimit(usage.ai_reports_used, usage.ai_reports_limit)
    );
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Monta os 3 cards do comparativo a partir do catálogo
   * público (mesma fonte de `settings-plans-page`) — sem CTA de
   * checkout aqui, só o link pra `/settings/plans`.
   */
  protected readonly planCards = computed<UsagePlanCardViewModel[]>(() => {
    const catalog = this.catalog();
    const currentPlan = this.subscription()?.effective_plan ?? 'free';
    if (!catalog) {
      return [];
    }

    return PLAN_ORDER.map((plan) => {
      const entry = catalog[plan];
      const isCurrent = plan === currentPlan;
      return {
        plan,
        nameKey: `subscription.planNames.${plan}`,
        badge: (isCurrent ? 'current' : plan === 'pro' ? 'popular' : plan === 'premium' ? 'premium' : 'free') as PlanCardBadge,
        taglineKey: TAGLINE_BY_PLAN[plan],
        priceCents: entry.monthly?.unit_amount_cents ?? 0,
        features: buildPlanFeatures(entry.limits),
        isCurrent,
      };
    });
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Dispara as 3 buscas necessárias pra montar a tela ao
   * montar o componente — uso de IA, assinatura atual e catálogo
   * público de planos (comparativo).
   */
  ngOnInit(): void {
    this.aiUsageService.load();
    this.subscriptionService.loadMySubscription();
    this.subscriptionService.loadCatalog();
  }
}
