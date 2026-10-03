import { Component, computed, input } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import { ChartModule } from 'primeng/chart';
import type { MonthlyEvolutionPoint } from '@amezia/shared-types';

const BRL_FORMATTER = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Resolve o valor computado de uma variável CSS do tema, ou
 * o padrão informado se não disponível (SSR) — mesmo helper usado pelo
 * irmão em `/home/adriano/Documentos/projetos/Amezia`, pra Chart.js
 * herdar as cores do tema claro/escuro sem hardcode.
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
 * Data: 2026-08-14
 * Descrição: Gráfico de linha da evolução mensal de despesas (Dashboard,
 * últimos 6 meses corridos) — renderizado via `p-chart` do PrimeNG
 * (wrapper de Chart.js), mesma biblioteca/estilo usados pelo irmão em
 * `/home/adriano/Documentos/projetos/Amezia` (curva suave `tension`,
 * tooltip nativo, cores herdadas do tema via variável CSS). Trocado do
 * SVG artesanal anterior a pedido do usuário em 2026-08-14 — ver
 * DIARIO.md. Quando `budgetLimit` vem preenchido, desenha também a
 * linha de referência do teto mensal (reta, verde) — o irmão faz o
 * mesmo em `buildMonthlyLineChartData()`, e a ausência dessa linha foi
 * apontada pelo usuário como uma regressão em 2026-08-14.
 */
@Component({
  selector: 'app-line-chart',
  standalone: true,
  imports: [TranslocoModule, ChartModule],
  templateUrl: './line-chart.component.html',
  styleUrl: './line-chart.component.css',
})
export class LineChartComponent {
  points = input.required<MonthlyEvolutionPoint[]>();
  budgetLimit = input<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `budgetLimit()` convertido pra número, só quando é um
   * teto de verdade (> 0) — controla a 2ª série (linha de referência)
   * do gráfico e a legenda.
   */
  protected readonly budgetValue = computed(() => {
    const parsed = Number(this.budgetLimit());
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `true` quando pelo menos um mês tem despesa > 0 —
   * controla o estado vazio do template (Chart.js não desenha nada útil
   * com uma série toda zerada).
   */
  protected readonly hasData = computed(() => this.points().some((point) => Number(point.total_expense) > 0));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Datasets do Chart.js — despesas (sempre) com o mesmo
   * `tension`/`cubicInterpolationMode` do irmão pra curva suave em vez
   * de segmentos retos, mais a linha reta do teto mensal (tracejada,
   * verde) quando `budgetValue()` existe.
   */
  protected readonly chartData = computed(() => {
    const data = this.points();
    const budget = this.budgetValue();
    const expenseColor = resolveThemeColor('--accent', '#4f46e5');
    const budgetColor = resolveThemeColor('--green', '#059669');
    const surfaceColor = resolveThemeColor('--bg-card', '#ffffff');
    const labels = data.map((point) => `${String(point.month).padStart(2, '0')}/${String(point.year).slice(2)}`);

    const datasets: unknown[] = [
      {
        label: 'Despesas',
        data: data.map((point) => Number(point.total_expense)),
        borderColor: expenseColor,
        backgroundColor: expenseColor,
        pointBackgroundColor: expenseColor,
        pointBorderColor: surfaceColor,
        pointHoverBackgroundColor: expenseColor,
        pointHoverBorderColor: surfaceColor,
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointHoverBorderWidth: 2,
        borderWidth: 3,
        tension: 0.36,
        cubicInterpolationMode: 'monotone',
        fill: false,
      },
    ];

    if (budget !== null) {
      datasets.push({
        label: 'Teto mensal',
        data: labels.map(() => budget),
        borderColor: budgetColor,
        backgroundColor: budgetColor,
        pointBackgroundColor: budgetColor,
        pointBorderColor: surfaceColor,
        pointHoverBackgroundColor: budgetColor,
        pointHoverBorderColor: surfaceColor,
        pointBorderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBorderWidth: 2,
        borderWidth: 2,
        borderDash: [6, 4],
        tension: 0,
        fill: false,
      });
    }

    return { labels, datasets };
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Opções do Chart.js — legenda escondida (só uma série),
   * tooltip formatado em pt-BR e eixo Y compacto, cores resolvidas das
   * variáveis CSS do tema ativo.
   */
  protected readonly chartOptions = computed(() => {
    const textColor = resolveThemeColor('--t2', '#64748b');
    const borderColor = resolveThemeColor('--bdr', 'rgba(15,23,42,0.08)');
    const tooltipBg = resolveThemeColor('--bg-elev', '#111827');
    const tooltipText = resolveThemeColor('--t1', '#e5e7eb');

    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 320, easing: 'easeOutQuart' },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltipBg,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          borderColor,
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
