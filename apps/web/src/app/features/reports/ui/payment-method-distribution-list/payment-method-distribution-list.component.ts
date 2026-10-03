import { Component, computed, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { PaymentMethodDistributionItem } from '@amezia/shared-types';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { paymentMethodLabelKey } from '../../../transactions/data-access/payment-method.model';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Resolve o valor computado de uma variável CSS do tema —
 * mesmo helper de `donut-chart.component.ts`/`line-chart.component.ts`.
 */
function resolveThemeColor(variable: string, fallback: string): string {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
  return value || fallback;
}

interface PaymentMethodDistributionRow {
  paymentMethod: string;
  labelKey: string;
  color: string;
  total: string;
  percentage: number;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Lista de distribuição por tipo de pagamento (Dashboard/
 * Reports, pedido direto do usuário, fora de qualquer build-context) —
 * mesmo visual de `category-distribution-list.component.ts` (barra +
 * %), mas tipo de pagamento não tem cor cadastrada no backend (ao
 * contrário de categoria), então a cor de cada linha vem de uma
 * paleta fixa do tema, ciclando pelos 5 tons semânticos já usados no
 * app (`--accent`/`--violet`/`--green`/`--amber`/`--red`) — como cada
 * linha também tem rótulo + barra própria, repetir cor a partir da 6ª
 * linha não compromete a leitura (diferente de um donut, onde cor é a
 * única pista visual). `clickable`/`itemClick` (2026-09-15) espelham
 * `category-distribution-list.component.ts` — só o Dashboard liga
 * (abre o modal de despesas daquele tipo de pagamento), Reports
 * continua só informativo.
 */
@Component({
  selector: 'app-payment-method-distribution-list',
  standalone: true,
  imports: [TranslocoModule, BrlAmountPipe],
  templateUrl: './payment-method-distribution-list.component.html',
  styleUrl: './payment-method-distribution-list.component.css',
})
export class PaymentMethodDistributionListComponent {
  items = input.required<PaymentMethodDistributionItem[]>();
  clickable = input(false);
  itemClick = output<PaymentMethodDistributionItem>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Junta cada item com a i18n key do rótulo (`payment_method`
   * bruto → `transactions.paymentMethod.*`, `paymentMethodLabelKey`
   * reaproveitado do catálogo compartilhado) e uma cor da paleta fixa,
   * na mesma ordem em que o backend já devolve (total desc).
   */
  protected readonly rows = computed<PaymentMethodDistributionRow[]>(() => {
    const palette = [
      resolveThemeColor('--accent', '#4f46e5'),
      resolveThemeColor('--violet', '#7c3aed'),
      resolveThemeColor('--green', '#059669'),
      resolveThemeColor('--amber', '#d97706'),
      resolveThemeColor('--red', '#dc2626'),
    ];
    return this.items().map((item, index) => ({
      paymentMethod: item.payment_method,
      labelKey: paymentMethodLabelKey(item.payment_method),
      color: palette[index % palette.length],
      total: item.total,
      percentage: item.percentage,
    }));
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Clique numa linha — só emite quando `clickable()` está
   * ligado (Dashboard), mesmo padrão de
   * `CategoryDistributionListComponent.onItemClick`.
   */
  protected onRowClick(row: PaymentMethodDistributionRow): void {
    if (this.clickable()) {
      this.itemClick.emit({ payment_method: row.paymentMethod, total: row.total, percentage: row.percentage });
    }
  }
}
