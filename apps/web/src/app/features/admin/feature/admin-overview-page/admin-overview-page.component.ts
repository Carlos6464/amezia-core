import { Component, OnInit, computed, inject } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import { ChartModule } from 'primeng/chart';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { AdminActivityService } from '../../data-access/admin-activity.service';
import { AdminStatsService } from '../../data-access/admin-stats.service';
import { ActivityFeedComponent } from '../../ui/activity-feed/activity-feed.component';
import { MrrChartComponent } from '../../ui/mrr-chart/mrr-chart.component';
import { StatCardComponent } from '../../ui/stat-card/stat-card.component';

const ACTIVITY_FEED_PAGE_SIZE = 8;

const INTEGER_FORMATTER = new Intl.NumberFormat('pt-BR');

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Resolve o valor computado de uma variável CSS do tema —
 * mesmo helper de `reports/ui/line-chart`, pra herdar a paleta preta do
 * admin (`--accent` sob `data-panel="admin"`) sem hardcode.
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
 * Data: 2026-08-15
 * Descrição: Visão Geral do Admin (build-context-06 §3.3) — KPIs de
 * usuários (total, novos no mês), usuários com WhatsApp vinculado,
 * total de feedbacks, e o gráfico de linha de novos usuários por mês
 * (últimos 6 meses). Escopo reduzido do protótipo original: sem
 * MRR/assinaturas/suporte (fora do MVP1, PRD §8).
 */
@Component({
  selector: 'app-admin-overview-page',
  standalone: true,
  imports: [
    TranslocoModule,
    ChartModule,
    StatCardComponent,
    MrrChartComponent,
    ActivityFeedComponent,
    BrlAmountPipe,
  ],
  templateUrl: './admin-overview-page.component.html',
  styleUrl: './admin-overview-page.component.css',
})
export class AdminOverviewPageComponent implements OnInit {
  private readonly statsService = inject(AdminStatsService);
  private readonly activityService = inject(AdminActivityService);

  readonly stats = this.statsService.stats;
  readonly loading = this.statsService.loading;
  readonly error = this.statsService.error;
  readonly activity = this.activityService.activity;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Total de assinaturas ativas (Pro + Trial Pro + Premium)
   * — sub-detalhe do card "Assinaturas ativas" (build-context-11
   * §3.1).
   */
  protected readonly activeSubscriptionsCount = computed(() => {
    const distribution = this.stats()?.subscriptions_by_plan;
    if (!distribution) {
      return 0;
    }
    return distribution.pro + distribution.trial_pro + distribution.premium;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Último ponto da série mensal (o mês corrente, já que a
   * série vem em ordem cronológica crescente) — 0 antes dos stats
   * carregarem.
   */
  protected readonly newUsersThisMonth = computed(() => {
    const series = this.stats()?.new_users_by_month ?? [];
    return series.length > 0 ? series[series.length - 1].count : 0;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: `true` quando pelo menos um mês tem cadastro > 0 —
   * controla o estado vazio do gráfico (Chart.js não desenha nada útil
   * com uma série toda zerada).
   */
  protected readonly hasChartData = computed(() =>
    (this.stats()?.new_users_by_month ?? []).some((point) => point.count > 0),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Datasets do Chart.js — cores resolvidas do tema ativo
   * (preto no admin), mesma curva suave (`tension`/`cubicInterpolationMode`)
   * do line-chart de Relatórios.
   */
  protected readonly chartData = computed(() => {
    const series = this.stats()?.new_users_by_month ?? [];
    const accentColor = resolveThemeColor('--accent', '#111827');
    const surfaceColor = resolveThemeColor('--bg-card', '#ffffff');

    return {
      labels: series.map((point) => this._formatMonthLabel(point.month)),
      datasets: [
        {
          label: 'Novos usuários',
          data: series.map((point) => point.count),
          borderColor: accentColor,
          backgroundColor: accentColor,
          pointBackgroundColor: accentColor,
          pointBorderColor: surfaceColor,
          pointHoverBackgroundColor: accentColor,
          pointHoverBorderColor: surfaceColor,
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          borderWidth: 3,
          tension: 0.36,
          cubicInterpolationMode: 'monotone',
          fill: false,
        },
      ],
    };
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Opções do Chart.js — legenda escondida (só uma série),
   * tooltip com contagem inteira (pt-BR), eixo Y sem casas decimais
   * (`precision: 0`, faz sentido só pra contagem de pessoas).
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
            label: (context: { parsed?: { y?: number } }) =>
              `${INTEGER_FORMATTER.format(Number(context.parsed?.y ?? 0))}`,
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
            precision: 0,
          },
        },
      },
    };
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Dispara a busca dos KPIs e do feed de atividade
   * recente (build-context-11, últimos `ACTIVITY_FEED_PAGE_SIZE`
   * itens) ao montar a página.
   */
  ngOnInit(): void {
    this.statsService.load();
    this.activityService.load(1, ACTIVITY_FEED_PAGE_SIZE);
  }

  protected formatCount(value: number | undefined): string {
    return INTEGER_FORMATTER.format(value ?? 0);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Formata `YYYY-MM-DD` (primeiro dia do mês, vindo do
   * backend) como rótulo curto `MM/AA` do eixo X — `T00:00:00` evita o
   * `new Date('YYYY-MM-DD')` interpretar a data como UTC e exibir o mês
   * anterior em fusos horários negativos.
   */
  private _formatMonthLabel(isoDate: string): string {
    const date = new Date(`${isoDate}T00:00:00`);
    return `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear()).slice(2)}`;
  }
}
