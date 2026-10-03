import { DecimalPipe } from '@angular/common';
import { Component, computed, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Cards "Despesas do período" e "Teto mensal"/"Comparativo"
 * (build-context-03 §2.9) — únicos dois mantidos do stats-strip do
 * protótipo (os outros dependiam de dados fora de escopo). O card de
 * teto só aparece preenchido quando o filtro ativo resolve para um
 * único mês (mesma regra do backend) — fora disso, convida a configurar.
 */
@Component({
  selector: 'app-transaction-stats-strip',
  standalone: true,
  imports: [TranslocoModule, DecimalPipe, BrlAmountPipe],
  templateUrl: './transaction-stats-strip.component.html',
  styleUrl: './transaction-stats-strip.component.css',
})
export class TransactionStatsStripComponent {
  totalAmount = input.required<string>();
  count = input.required<number>();
  budgetLimit = input<string | null>(null);
  budgetUsedPercentage = input<number | null>(null);

  editBudget = output<void>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Percentual travado em [0, 100] só para a largura da
   * barra — o número exibido em texto continua sem teto, para o usuário
   * ver o quanto realmente estourou.
   */
  readonly barWidth = computed(() => {
    const percentage = this.budgetUsedPercentage();
    if (percentage === null) {
      return 0;
    }
    return Math.min(percentage, 100);
  });

  readonly isOverBudget = computed(() => (this.budgetUsedPercentage() ?? 0) > 100);
}
