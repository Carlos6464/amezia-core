import type { BillingCycle, PaidPlan, Plan, PlanLimits } from '@amezia/shared-types';

import type { PlanCardFeature } from '../ui/plan-card/plan-card.component';

export type { BillingCycle, PaidPlan, Plan, PlanLimits, Subscription } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Ordem de exibição fixa dos 3 planos (build-context-09
 * §3.2) — reaproveitada por `register-plan-page`/`settings-plans-page`
 * pra montar a grade de comparação sempre na mesma ordem.
 */
export const PLAN_ORDER: Plan[] = ['free', 'pro', 'premium'];

export const PAID_PLAN_ORDER: PaidPlan[] = ['pro', 'premium'];

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Ranking numérico do plano — usado só pra decidir se um
 * upgrade/downgrade está subindo ou descendo de nível (nunca exposto
 * na UI).
 */
export const PLAN_RANK: Record<Plan, number> = { free: 0, pro: 1, premium: 2 };

export const DEFAULT_BILLING_CYCLE: BillingCycle = 'monthly';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Monta a lista de features de um plano a partir dos
 * `PlanLimits` reais (nunca hardcoded) — reaproveitado por
 * `register-plan-page`/`settings-plans-page`, pra nunca divergirem no
 * que mostram. `null` em qualquer limite vira "ilimitado" (chave de
 * tradução própria, sem interpolar número nenhum). Bot WhatsApp e
 * exportação CSV sempre aparecem como incluídos (`included: true`) —
 * decisão de escopo do build-context-09: no Free eles têm limite
 * mensal, nunca ficam indisponíveis por completo (diferente do que os
 * protótipos desatualizados mostravam).
 */
export function buildPlanFeatures(limits: PlanLimits): PlanCardFeature[] {
  return [
    { labelKey: 'subscription.features.dashboard', included: true },
    { labelKey: 'subscription.features.unlimitedTransactions', included: true },
    { labelKey: 'subscription.features.unlimitedCategories', included: true },
    limits.ai_conversations_per_month === null
      ? { labelKey: 'subscription.features.aiConversationsUnlimited', included: true }
      : {
          labelKey: 'subscription.features.aiConversations',
          labelParams: { count: limits.ai_conversations_per_month },
          included: true,
        },
    limits.ai_reports_per_month === null
      ? { labelKey: 'subscription.features.aiReportsUnlimited', included: true }
      : {
          labelKey: 'subscription.features.aiReports',
          labelParams: { count: limits.ai_reports_per_month },
          included: true,
        },
    limits.whatsapp_bot_messages_per_month === null
      ? { labelKey: 'subscription.features.whatsappUnlimited', included: true }
      : {
          labelKey: 'subscription.features.whatsappLimited',
          labelParams: { count: limits.whatsapp_bot_messages_per_month },
          included: true,
        },
    limits.csv_exports_per_month === null
      ? { labelKey: 'subscription.features.csvExportUnlimited', included: true }
      : {
          labelKey: 'subscription.features.csvExportLimited',
          labelParams: { count: limits.csv_exports_per_month },
          included: true,
        },
    { labelKey: 'subscription.features.prioritySupport', included: limits.priority_support_enabled },
  ];
}
