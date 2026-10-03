import { Component, computed, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';

export type PlanCardBadge = 'free' | 'popular' | 'premium' | 'current';
export type PlanCardCtaVariant = 'free' | 'popular' | 'premium' | 'current' | 'upgrade' | 'downgrade';

export interface PlanCardFeature {
  labelKey: string;
  labelParams?: Record<string, string | number>;
  included: boolean;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Card "burro" de 1 plano (build-context-09 §3.2, T16) —
 * reaproveitado por `register-plan-page` (grade de 3, sem estado
 * "atual") e `settings-plans-page` (grade de 3, com "atual"/upgrade/
 * downgrade). Não sabe nada sobre qual tela o usa nem chama nenhum
 * serviço — só recebe dados prontos e emite `ctaClick`.
 */
@Component({
  selector: 'app-plan-card',
  standalone: true,
  imports: [TranslocoModule, BrlAmountPipe],
  templateUrl: './plan-card.component.html',
  styleUrl: './plan-card.component.css',
})
export class PlanCardComponent {
  readonly nameKey = input.required<string>();
  readonly badge = input<PlanCardBadge>('free');
  readonly taglineKey = input.required<string>();
  readonly priceCents = input<number>(0);
  readonly billingCycle = input<'monthly' | 'annual'>('monthly');
  readonly annualMonthlyEquivalentCents = input<number | null>(null);
  readonly features = input.required<PlanCardFeature[]>();
  readonly ctaLabelKey = input.required<string>();
  readonly ctaVariant = input<PlanCardCtaVariant>('free');
  readonly ctaDisabled = input(false);
  readonly highlighted = input(false);

  readonly ctaClick = output<void>();

  protected readonly priceReais = computed(() => this.priceCents() / 100);
  protected readonly annualMonthlyEquivalentReais = computed(() => {
    const cents = this.annualMonthlyEquivalentCents();
    return cents === null ? null : cents / 100;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Emite `ctaClick` só quando o botão não está desabilitado
   * (plano atual, por exemplo, não deve disparar nada ao clicar).
   */
  onCtaClick(): void {
    if (this.ctaDisabled()) {
      return;
    }
    this.ctaClick.emit();
  }
}
