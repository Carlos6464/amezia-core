import { Component, computed, input } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import { ChartModule } from 'primeng/chart';
import type { MonthlyPaidPendingPoint } from '@amezia/shared-types';

const BRL_FORMATTER = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

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

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Gráfico de barra dupla "Pago x Pendente" por mês
 * (Dashboard/Reports, últimos 6 meses corridos — pedido direto do
 * usuário, fora de qualquer build-context) — `p-chart` do PrimeNG
 * (`type="bar"`, duas séries agrupadas), mesma biblioteca/estilo já
 * usados por `donut-chart`/`line-chart` (Chart.js, cores herdadas do
 * tema via variável CSS, nunca um `<canvas>` artesanal — decisão já
 * tomada nesses dois componentes em 2026-08-14).
 */
@Component({
  selector: 'app-paid-pending-bar-chart',
  standalone: true,
  imports: [TranslocoModule, ChartModule],
  templateUrl: './paid-pending-bar-chart.component.html',
  styleUrl: './paid-pending-bar-chart.component.css',
})
export class PaidPendingBarChartComponent {
  points = input.required<MonthlyPaidPendingPoint[]>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: `true` quando pelo menos um mês tem pago ou pendente > 0
   * — controla o estado vazio do template.
   */
  protected readonly hasData = computed(() =>
    this.points().some((point) => Number(point.total_paid) > 0 || Number(point.total_pending) > 0),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: 2 datasets do Chart.js (Pago/Pendente), mesmo formato de
   * rótulo de mês de `line-chart.component.ts` (`MM/AA`).
   */
  protected readonly chartData = computed(() => {
    const data = this.points();
    const paidColor = resolveThemeColor('--green', '#059669');
    const pendingColor = resolveThemeColor('--amber', '#d97706');
    const labels = data.map((point) => `${String(point.month).padStart(2, '0')}/${String(point.year).slice(2)}`);

    return {
      labels,
      datasets: [
        {
          label: 'Pago',
          data: data.map((point) => Number(point.total_paid)),
          backgroundColor: paidColor,
          borderRadius: 4,
          maxBarThickness: 22,
        },
        {
          label: 'Pendente',
          data: data.map((point) => Number(point.total_pending)),
          backgroundColor: pendingColor,
          borderRadius: 4,
          maxBarThickness: 22,
        },
      ],
    };
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Opções do Chart.js — legenda escondida (o card mostra a
   * própria abaixo, mesmo padrão de `line-chart`'s `chart-legend`),
   * tooltip formatado em pt-BR, barras agrupadas lado a lado por mês
   * (`grouped`, padrão do Chart.js pra múltiplos datasets num eixo de
   * categoria).
   */
  protected readonly chartOptions = computed(() => {
    const textColor = resolveThemeColor('--t2', '#64748b');

    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 320, easing: 'easeOutQuart' },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: resolveThemeColor('--bg-elev', '#111827'),
          titleColor: resolveThemeColor('--t1', '#e5e7eb'),
          bodyColor: resolveThemeColor('--t1', '#e5e7eb'),
          borderColor: resolveThemeColor('--bdr', 'rgba(15,23,42,0.08)'),
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (context: { dataset?: { label?: string }; parsed?: { y?: number } }) =>
              `${context.dataset?.label ?? ''}: ${BRL_FORMATTER.format(Number(context.parsed?.y ?? 0))}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: { color: textColor, font: { size: 11, weight: 600 } },
        },
        y: {
          beginAtZero: true,
          grid: { display: false, drawBorder: false },
          border: { display: false },
          ticks: {
            color: textColor,
            padding: 10,
            font: { size: 11 },
            callback: (value: number | string) => BRL_FORMATTER.format(Number(value)),
          },
        },
      },
    };
  });
}
