import { Component, computed, inject, input } from '@angular/core';
import { TranslocoService } from '@jsverse/transloco';
import { ChartModule } from 'primeng/chart';
import type { PlanDistribution } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-11
 * Descrição: Resolve o valor computado de uma variável CSS do tema —
 * mesmo helper de `admin-overview-page`, pra herdar a paleta preta do
 * admin sem hardcode.
 */
function resolveThemeColor(variable: string, fallback: string): string {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
  return value || fallback;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-11
 * Descrição: Gráfico de barras horizontais "Usuários por plano"
 * (build-context-11 §3.1/T7) — Free/Pro/Trial Pro/Premium, trial
 * contado à parte do Pro pago de verdade (mesmo critério do
 * `PlanDistributionResponse` do backend).
 */
@Component({
  selector: 'app-mrr-chart',
  standalone: true,
  imports: [ChartModule],
  templateUrl: './mrr-chart.component.html',
  styleUrl: './mrr-chart.component.css',
})
export class MrrChartComponent {
  private readonly transloco = inject(TranslocoService);

  readonly distribution = input.required<PlanDistribution>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Dataset do Chart.js — 1 barra por bucket
   * (Free/Trial Pro/Pro/Premium), cor única resolvida do tema ativo.
   */
  protected readonly chartData = computed(() => {
    const distribution = this.distribution();
    const accentColor = resolveThemeColor('--accent', '#111827');
    return {
      labels: [
        this.transloco.translate('admin.overview.planNames.free'),
        this.transloco.translate('admin.overview.planNames.trialPro'),
        this.transloco.translate('admin.overview.planNames.pro'),
        this.transloco.translate('admin.overview.planNames.premium'),
      ],
      datasets: [
        {
          data: [distribution.free, distribution.trial_pro, distribution.pro, distribution.premium],
          backgroundColor: accentColor,
          borderRadius: 4,
          barThickness: 18,
        },
      ],
    };
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Opções do Chart.js — eixo invertido (`indexAxis: 'y'`)
   * pras barras ficarem horizontais, sem legenda (só 1 série).
   */
  protected readonly chartOptions = computed(() => {
    const textColor = resolveThemeColor('--t2', '#64748b');
    const borderColor = resolveThemeColor('--bdr', 'rgba(15,23,42,0.08)');

    return {
      indexAxis: 'y' as const,
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { color: textColor, font: { size: 11 }, precision: 0 },
          grid: { color: borderColor },
        },
        y: {
          ticks: { color: textColor, font: { size: 11, weight: 600 } },
          grid: { display: false },
        },
      },
    };
  });
}
