import { Component, input } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { MonthlyUsagePoint } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Tabela "burra" de histórico mensal de uso de IA
 * (build-context-10 §3.2, T11) — conversas/relatórios dos últimos
 * meses, mais recente por último (mesma ordem que a API já devolve).
 */
@Component({
  selector: 'app-usage-history-table',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './usage-history-table.component.html',
  styleUrl: './usage-history-table.component.css',
})
export class UsageHistoryTableComponent {
  readonly history = input.required<MonthlyUsagePoint[]>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Formata `YYYY-MM-DD` (1º dia do mês, vindo do backend)
   * como rótulo `MM/AAAA` — mesmo cuidado de `admin-overview-page`
   * (`T00:00:00` evita o fuso horário deslocar pro mês anterior).
   */
  protected formatMonth(isoDate: string): string {
    const date = new Date(`${isoDate}T00:00:00`);
    return `${String(date.getMonth() + 1).padStart(2, '0')}/${date.getFullYear()}`;
  }
}
