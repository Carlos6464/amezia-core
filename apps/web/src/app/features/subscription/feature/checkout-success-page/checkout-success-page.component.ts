import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import type { BillingCycle, Plan } from '@amezia/shared-types';

import { ThemeService } from '../../../../core/theme/theme.service';

interface Benefit {
  iconKey: 'whatsapp' | 'ai' | 'reports' | 'dashboard' | 'unlimitedAi' | 'prioritySupport' | 'categories';
  labelKey: string;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Cada plano tem seu próprio array COMPLETO e independente
 * de benefícios — o protótipo (`screem/checkout-success`) tenta reaproveitar
 * o array do Pro pra montar o do Premium acessando por índice
 * (`querySelectorAll(...)[1]`/`[3]`), um bug real que quebra se a
 * ordem/quantidade dos itens mudar. build-context-09 §3.3 pede
 * explicitamente pra não portar isso — daqui pra baixo, 3 listas
 * soltas, sem nenhuma dependência entre si.
 */
const BENEFITS_BY_PLAN: Record<Plan, Benefit[]> = {
  free: [
    { iconKey: 'dashboard', labelKey: 'subscription.checkoutSuccess.benefits.free.dashboard' },
    { iconKey: 'ai', labelKey: 'subscription.checkoutSuccess.benefits.free.ai' },
    { iconKey: 'categories', labelKey: 'subscription.checkoutSuccess.benefits.free.categories' },
  ],
  pro: [
    { iconKey: 'whatsapp', labelKey: 'subscription.checkoutSuccess.benefits.pro.whatsapp' },
    { iconKey: 'ai', labelKey: 'subscription.checkoutSuccess.benefits.pro.ai' },
    { iconKey: 'reports', labelKey: 'subscription.checkoutSuccess.benefits.pro.reports' },
  ],
  premium: [
    { iconKey: 'whatsapp', labelKey: 'subscription.checkoutSuccess.benefits.premium.whatsapp' },
    { iconKey: 'unlimitedAi', labelKey: 'subscription.checkoutSuccess.benefits.premium.unlimitedAi' },
    {
      iconKey: 'prioritySupport',
      labelKey: 'subscription.checkoutSuccess.benefits.premium.prioritySupport',
    },
  ],
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Confirmação pós-pagamento (build-context-09 §3.1/T19) —
 * rota pública standalone (sem `AppShellComponent`/`authGuard`, mesmo
 * espírito de `SharedReportPageComponent`), pra onde o `success_url`
 * da Checkout Session do Stripe redireciona
 * (`StartCheckoutUseCase._start_new_checkout`). Não faz nenhuma
 * chamada HTTP — só lê `?plan=`/`?billing=` da própria URL pra montar
 * a mensagem certa; o estado real da assinatura é confirmado pelo
 * webhook, que roda em paralelo (§2.5 passo 4).
 */
@Component({
  selector: 'app-checkout-success-page',
  standalone: true,
  imports: [TranslocoModule, RouterLink],
  templateUrl: './checkout-success-page.component.html',
  styleUrl: './checkout-success-page.component.css',
})
export class CheckoutSuccessPageComponent {
  private readonly route = inject(ActivatedRoute);
  protected readonly themeService = inject(ThemeService);

  protected readonly plan: Plan;
  protected readonly billingCycle: BillingCycle;
  protected readonly benefits: Benefit[];
  protected readonly confettiDots = Array.from({ length: 18 }, (_, index) => this.buildDot(index));

  constructor() {
    const planParam = this.route.snapshot.queryParamMap.get('plan');
    this.plan = planParam === 'pro' || planParam === 'premium' ? planParam : 'free';
    this.billingCycle = this.route.snapshot.queryParamMap.get('billing') === 'annual' ? 'annual' : 'monthly';
    this.benefits = BENEFITS_BY_PLAN[this.plan];
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Gera a posição/cor/atraso de 1 ponto do confete — puro
   * enfeite visual, sem estado nem efeito colateral.
   */
  private buildDot(index: number): { left: string; color: string; delay: string; duration: string; size: string } {
    const colors = ['#6366f1', '#34d399', '#fbbf24', '#60a5fa', '#a78bfa', '#f87171'];
    return {
      left: `${5 + Math.random() * 90}%`,
      color: colors[index % colors.length],
      delay: `${(Math.random() * 0.8).toFixed(2)}s`,
      duration: `${(1.5 + Math.random() * 0.8).toFixed(2)}s`,
      size: `${4 + Math.random() * 5}px`,
    };
  }
}
