import type { DashboardCard, DashboardCardPreference } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Layout "de fábrica" do Dashboard (pedido direto do
 * usuário, fora de qualquer build-context) — todos os 6 cards
 * personalizáveis visíveis, na mesma ordem em que sempre apareceram na
 * tela. Usado quando o backend devolve `layout: null` (usuário nunca
 * personalizou) e como base pra mesclar contas que personalizaram antes
 * de um card novo existir (`mergeDashboardLayout`).
 */
export const DEFAULT_DASHBOARD_LAYOUT: DashboardCardPreference[] = [
  { card: 'monthly_trend', visible: true },
  { card: 'category_composition', visible: true },
  { card: 'category_distribution', visible: true },
  { card: 'recent_transactions', visible: true },
  { card: 'payment_method_distribution', visible: true },
  { card: 'paid_pending', visible: true },
];

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Rótulo (i18n key) de cada card — usado no painel de
 * personalização, onde os 6 cards aparecem numa lista com nome +
 * toggle, independente de estarem visíveis ou não na tela.
 */
export const DASHBOARD_CARD_LABEL_KEYS: Record<DashboardCard, string> = {
  monthly_trend: 'reports.dashboard.trendTitle',
  category_composition: 'reports.dashboard.compositionTitle',
  category_distribution: 'reports.dashboard.distributionTitle',
  recent_transactions: 'reports.dashboard.recentTitle',
  payment_method_distribution: 'reports.dashboard.paymentMethodTitle',
  paid_pending: 'reports.dashboard.paidPendingTitle',
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Mescla o layout salvo do usuário com o padrão — qualquer
 * card do padrão que não esteja na lista salva (ex.: um card novo,
 * adicionado depois da última vez que o usuário personalizou) entra no
 * final, visível, em vez de desaparecer silenciosamente da tela. `null`
 * (nunca personalizou) devolve o padrão inteiro.
 */
export function mergeDashboardLayout(
  stored: DashboardCardPreference[] | null,
): DashboardCardPreference[] {
  if (stored === null) {
    return DEFAULT_DASHBOARD_LAYOUT;
  }
  const knownCards = new Set(stored.map((preference) => preference.card));
  const missing = DEFAULT_DASHBOARD_LAYOUT.filter((preference) => !knownCards.has(preference.card));
  return [...stored, ...missing];
}
