import { Component, computed, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import { ChartModule } from 'primeng/chart';
import type { CategoryDistributionItem } from '@amezia/shared-types';

const BRL_FORMATTER = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Resolve o valor computado de uma variável CSS do tema, ou
 * o padrão informado se não disponível (SSR) — mesmo helper de
 * `line-chart.component.ts`.
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
 * Descrição: Donut de composição por categoria (Dashboard) — renderizado
 * via `p-chart` do PrimeNG (`type="doughnut"`, Chart.js), mesma
 * biblioteca/estilo do irmão em
 * `/home/adriano/Documentos/projetos/Amezia` (rótulo central sobreposto
 * em CSS, tooltip nativo com percentual). Recebe a distribuição já
 * pronta (`CategoryDistributionItem[]`, ordenada por total desc) e o
 * rótulo central formatado pela página. Trocado do SVG artesanal
 * anterior a pedido do usuário em 2026-08-14 — ver DIARIO.md. Emite
 * `sliceClick` ao clicar numa fatia (2026-08-18) — quem monta o modal
 * de detalhe é o card chamador (Dashboard), este componente só avisa
 * qual categoria foi clicada.
 */
@Component({
  selector: 'app-donut-chart',
  standalone: true,
  imports: [TranslocoModule, ChartModule],
  templateUrl: './donut-chart.component.html',
  styleUrl: './donut-chart.component.css',
})
export class DonutChartComponent {
  items = input.required<CategoryDistributionItem[]>();
  centerLabel = input.required<string>();
  sliceClick = output<CategoryDistributionItem>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `true` quando há ao menos uma categoria a desenhar —
   * controla o estado vazio do template.
   */
  protected readonly hasData = computed(() => this.items().length > 0);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Dataset do Chart.js — cores literais de cada categoria
   * (`item.color`, já vêm do backend), sem resolução de variável CSS.
   */
  protected readonly chartData = computed(() => {
    const items = this.items();
    const surfaceColor = resolveThemeColor('--bg-card', '#ffffff');
    const colors = items.map((item) => item.color);
    return {
      labels: items.map((item) => item.name),
      datasets: [
        {
          data: items.map((item) => Number(item.total)),
          backgroundColor: colors,
          hoverBackgroundColor: colors,
          borderColor: surfaceColor,
          borderWidth: 3,
          spacing: 2,
          hoverOffset: 6,
        },
      ],
    };
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Opções do Chart.js — anel largo (`cutout: 78%`) pra dar
   * espaço ao rótulo central sobreposto em CSS, legenda escondida
   * (a lista de categorias já mostra a legenda ao lado) e tooltip com
   * valor + percentual.
   */
  protected readonly chartOptions = computed(() => {
    const borderColor = resolveThemeColor('--bdr', 'rgba(15,23,42,0.08)');
    const tooltipBg = resolveThemeColor('--bg-elev', '#111827');
    const tooltipText = resolveThemeColor('--t1', '#e5e7eb');
    const items = this.items();

    return {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '78%',
      radius: '92%',
      animation: { duration: 280, easing: 'easeOutQuart' },
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
            label: (context: { dataIndex: number; label?: string; parsed?: number }) => {
              const value = Number(context.parsed ?? 0);
              const percentage = items[context.dataIndex]?.percentage ?? 0;
              return `${context.label}: ${BRL_FORMATTER.format(value)} (${percentage.toFixed(0)}%)`;
            },
          },
        },
      },
    };
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Clique numa fatia do donut (`p-chart` `(onDataSelect)`,
   * PrimeNG) — reemite a categoria correspondente pro card poder abrir
   * o modal de transações daquele mês (pedido do usuário, Dashboard
   * "mais rico"). `event.element.index` é o índice do ponto de dado
   * clicado, na mesma ordem de `items()` usada em `chartData()`.
   */
  protected onChartClick(event: { element?: { index: number } }): void {
    const index = event.element?.index;
    if (index === undefined) {
      return;
    }
    const item = this.items()[index];
    if (item) {
      this.sliceClick.emit(item);
    }
  }
}
