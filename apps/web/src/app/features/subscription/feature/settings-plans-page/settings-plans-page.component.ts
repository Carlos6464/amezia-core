import { Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import type { BillingCycle, PaidPlan, Plan } from '@amezia/shared-types';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ConfirmDialogModule } from 'primeng/confirmdialog';

import { AuthService } from '../../../../core/auth/auth.service';
import { BrDatePipe } from '../../../../shared/pipes/br-date.pipe';
import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { PLAN_RANK, buildPlanFeatures } from '../../data-access/subscription.model';
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
  ctaDisabled: boolean;
}

type StatusBadgeKind = 'free' | 'trial' | 'active' | 'past_due' | 'canceled';

const TAGLINE_BY_PLAN: Record<Plan, string> = {
  free: 'subscription.registerPlan.tagline.free',
  pro: 'subscription.registerPlan.tagline.pro',
  premium: 'subscription.registerPlan.tagline.premium',
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: "Plano atual" + grade comparativa + cancelamento
 * (build-context-09 §3.1/T18) — nova aba "Planos" em Configurações.
 * `billing-cycle-toggle` aqui é só pra comparar preço visualmente
 * (§3.3 da spec) — nunca dispara checkout sozinho, só os CTAs dos
 * cards fazem isso.
 */
@Component({
  selector: 'app-settings-plans-page',
  standalone: true,
  imports: [
    TranslocoModule,
    PlanCardComponent,
    BillingCycleToggleComponent,
    BrDatePipe,
    BrlAmountPipe,
    ConfirmDialogModule,
  ],
  templateUrl: './settings-plans-page.component.html',
  styleUrl: './settings-plans-page.component.css',
})
export class SettingsPlansPageComponent {
  private readonly subscriptionService = inject(SubscriptionService);
  private readonly authService = inject(AuthService);
  private readonly messageService = inject(MessageService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly transloco = inject(TranslocoService);
  private readonly router = inject(Router);

  protected readonly subscription = this.subscriptionService.mySubscription;
  protected readonly catalog = this.subscriptionService.catalog;
  protected readonly loading = computed(
    () => this.subscriptionService.loadingMySubscription() || this.subscriptionService.loadingCatalog(),
  );
  protected readonly actionLoading = signal(false);
  protected readonly billingCycle = signal<BillingCycle>('monthly');

  protected readonly annualAvailable = computed(() => {
    const catalog = this.catalog();
    return !!catalog && (catalog.pro.annual !== null || catalog.premium.annual !== null);
  });

  protected readonly statusBadge = computed<StatusBadgeKind>(() => {
    const sub = this.subscription();
    if (!sub || sub.effective_plan === 'free') {
      return 'free';
    }
    if (sub.status === 'trialing') return 'trial';
    if (sub.status === 'past_due') return 'past_due';
    if (sub.status === 'canceled') return 'canceled';
    return 'active';
  });

  protected readonly currentPriceCents = computed(() => {
    const sub = this.subscription();
    const catalog = this.catalog();
    if (!sub || !catalog || sub.effective_plan === 'free') {
      return 0;
    }
    const entry = catalog[sub.effective_plan];
    const price = sub.billing_cycle === 'annual' ? entry.annual : entry.monthly;
    return price?.unit_amount_cents ?? 0;
  });

  protected readonly planCards = computed<PlanCardViewModel[]>(() => {
    const catalog = this.catalog();
    const sub = this.subscription();
    if (!catalog || !sub) {
      return [];
    }
    const cycle = this.billingCycle();
    const currentPlan = sub.effective_plan;

    return (['free', 'pro', 'premium'] as const).map((plan) => {
      const entry = catalog[plan];
      const activePrice = cycle === 'annual' ? entry.annual : entry.monthly;
      const priceCents = activePrice?.unit_amount_cents ?? 0;
      const annualMonthlyEquivalentCents =
        cycle === 'annual' && entry.annual ? Math.round(entry.annual.unit_amount_cents / 12) : null;
      const isCurrent = plan === currentPlan;

      let ctaLabelKey: string;
      let ctaVariant: PlanCardCtaVariant;
      if (isCurrent) {
        ctaLabelKey = 'subscription.settingsPlans.cta.current';
        ctaVariant = 'current';
      } else if (PLAN_RANK[plan] > PLAN_RANK[currentPlan]) {
        ctaLabelKey = 'subscription.settingsPlans.cta.upgrade';
        ctaVariant = 'upgrade';
      } else if (plan === 'free') {
        ctaLabelKey = 'subscription.settingsPlans.cta.cancelToFree';
        ctaVariant = 'downgrade';
      } else {
        ctaLabelKey = 'subscription.settingsPlans.cta.downgrade';
        ctaVariant = 'downgrade';
      }

      return {
        plan,
        nameKey: `subscription.planNames.${plan}`,
        badge: isCurrent ? 'current' : plan === 'pro' ? 'popular' : plan === 'premium' ? 'premium' : 'free',
        taglineKey: TAGLINE_BY_PLAN[plan],
        priceCents,
        annualMonthlyEquivalentCents,
        features: buildPlanFeatures(entry.limits),
        ctaLabelKey,
        ctaVariant,
        ctaDisabled: isCurrent,
      };
    });
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Expulsa desta tela quem tem acesso de teste Premium
   * vitalício concedido pelo admin, ou quem tem papel `admin`
   * navegando no app do cliente comum (pedido direto do usuário: as
   * duas contas não têm assinatura real por trás pra mexer em
   * checkout/portal de cobrança). Reage aos Signals em vez de um
   * `canActivate` guard de propósito — a essa altura o shell (rota pai)
   * já disparou `loadMySubscription()` no próprio `ngOnInit`, mas a
   * resposta pode ainda não ter chegado quando este componente é
   * criado (ex.: link direto pra `/settings/plans`); um guard baseado
   * em Observable correria risco de checar `mySubscription()` antes do
   * dado existir. O `effect()` dispara de novo assim que o Signal for
   * populado, então o redirect acontece de forma confiável mesmo nesse
   * caso, sem duplicar a chamada HTTP.
   */
  private readonly redirectAwayFromAdminTestAccess = effect(() => {
    const isAdmin = this.authService.currentUser()?.role === 'admin';
    const isAdminTestAccess = this.subscriptionService.mySubscription()?.is_admin_test_access;
    if (isAdmin || isAdminTestAccess) {
      this.router.navigateByUrl('/settings');
    }
  });

  constructor() {
    this.subscriptionService.loadMySubscription();
    this.subscriptionService.loadCatalog();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Clique num CTA da grade comparativa — "voltar pro Free"
   * nunca passa por `POST /subscriptions/checkout` (o endpoint só
   * aceita Pro/Premium, StartCheckoutUseCase §2.5), então esse caso
   * abre o Customer Portal (mesmo caminho de "Cancelar assinatura")
   * em vez de tentar um checkout que o backend rejeitaria.
   */
  onPlanCtaClick(plan: Plan): void {
    if (plan === 'free') {
      this.confirmCancel();
      return;
    }
    this.startCheckout(plan as PaidPlan);
  }

  private startCheckout(plan: PaidPlan): void {
    this.actionLoading.set(true);
    this.subscriptionService.checkout({ plan, billing_cycle: this.billingCycle() }).subscribe({
      next: (result) => {
        this.actionLoading.set(false);
        if (result.checkout_url) {
          window.location.href = result.checkout_url;
          return;
        }
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('subscription.settingsPlans.toastTitle'),
          detail: this.transloco.translate('subscription.settingsPlans.planChanged'),
        });
      },
      error: () => {
        this.actionLoading.set(false);
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('subscription.settingsPlans.toastTitle'),
          detail: this.transloco.translate('subscription.settingsPlans.errors.checkoutFailed'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: "Gerenciar assinatura" — abre o Customer Portal do
   * Stripe (troca de cartão, faturas, cancelamento), sempre com
   * redirect de página inteira no sucesso.
   */
  protected openBillingPortal(): void {
    this.actionLoading.set(true);
    this.subscriptionService.openBillingPortal().subscribe({
      next: (result) => {
        window.location.href = result.url;
      },
      error: () => {
        this.actionLoading.set(false);
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('subscription.settingsPlans.toastTitle'),
          detail: this.transloco.translate('subscription.settingsPlans.errors.portalFailed'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: "Cancelar assinatura"/"Fazer downgrade pra Free" — pede
   * confirmação antes de abrir o portal (mesmo padrão de
   * `ConfirmationService` já usado pra exclusão de transação/conta),
   * já que cancelar é uma ação destrutiva do ponto de vista do usuário.
   */
  protected confirmCancel(): void {
    this.confirmationService.confirm({
      header: this.transloco.translate('subscription.settingsPlans.cancelConfirm.header'),
      message: this.transloco.translate('subscription.settingsPlans.cancelConfirm.message'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: this.transloco.translate('subscription.settingsPlans.cancelConfirm.accept'),
      rejectLabel: this.transloco.translate('subscription.settingsPlans.cancelConfirm.reject'),
      acceptButtonProps: { severity: 'danger' },
      rejectButtonProps: { severity: 'secondary', outlined: true },
      accept: () => this.openBillingPortal(),
    });
  }
}
