import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { BreakpointService } from '../../../../core/viewport/breakpoint.service';
import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { ReportsStateService } from '../../data-access/reports-state.service';
import type { ReportsDateRange } from '../../data-access/reports.models';
import { AiNarrativeCardComponent } from '../../ui/ai-narrative-card/ai-narrative-card.component';
import { CategoryDistributionListComponent } from '../../ui/category-distribution-list/category-distribution-list.component';
import { MetricCardComponent } from '../../ui/metric-card/metric-card.component';
import { PaidPendingBarChartComponent } from '../../ui/paid-pending-bar-chart/paid-pending-bar-chart.component';
import { PaymentMethodDistributionListComponent } from '../../ui/payment-method-distribution-list/payment-method-distribution-list.component';
import { PeriodRangePickerComponent } from '../../ui/period-range-picker/period-range-picker.component';
import { ReportCategorySelectComponent } from '../../ui/report-category-select/report-category-select.component';
import { TransactionsTableComponent } from '../../ui/transactions-table/transactions-table.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Quantidade de meses cobertos por um intervalo ISO
 * (inclusive nas duas pontas) — usado para calcular a "média mensal".
 */
function monthsBetween(dateFrom: string, dateTo: string): number {
  const [fromYear, fromMonth] = dateFrom.split('-').map(Number);
  const [toYear, toMonth] = dateTo.split('-').map(Number);
  return (toYear - fromYear) * 12 + (toMonth - fromMonth) + 1;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Tela de análise aprofundada (`/reports`, build-context-05
 * §3.4) — filtro De/Até + categoria, stats-strip, narrativa IA, ranking
 * completo de categorias e tabela paginada de transações, com export
 * CSV. Sem filtro de tipo: produto é expense-only (2026-08-14). Filtros
 * ficam em rascunho local até o usuário clicar "Aplicar" (mesmo padrão
 * de busca só sob demanda de `TransactionFilterBarComponent`), evitando
 * uma requisição por tecla/clique. No mobile (2026-08-15, pedido do
 * usuário: "igual os outros"), o filtro de categoria + Aplicar/Limpar
 * migram pra um bottom sheet de tela cheia (mesmo padrão de
 * `TransactionFilterBarComponent`/`CategoryFilterBarComponent`), aberto
 * por um botão "Filtro" no cabeçalho — mas o navegador De/Até continua
 * sempre visível na tela principal, fora do sheet (o usuário pediu
 * explicitamente essa exceção, já que trocar o período é a ação mais
 * comum da tela).
 */
@Component({
  selector: 'app-reports-page',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    TranslocoModule,
    BrlAmountPipe,
    PeriodRangePickerComponent,
    ReportCategorySelectComponent,
    MetricCardComponent,
    AiNarrativeCardComponent,
    CategoryDistributionListComponent,
    PaymentMethodDistributionListComponent,
    PaidPendingBarChartComponent,
    TransactionsTableComponent,
  ],
  templateUrl: './reports-page.component.html',
  styleUrl: './reports-page.component.css',
})
export class ReportsPageComponent implements OnInit {
  protected readonly state = inject(ReportsStateService);
  protected readonly breakpoint = inject(BreakpointService);

  // Rascunho local — só propaga pro ReportsStateService ao clicar "Aplicar"
  protected readonly draftRange = signal<ReportsDateRange>(this.state.periodRange());
  protected readonly draftCategoryId = signal(this.state.filters().categoryId);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Controla a visibilidade do bottom sheet mobile de
   * filtro (categoria + Aplicar/Limpar) — mesmo padrão de
   * `TransactionFilterBarComponent.sheetOpen`.
   */
  protected readonly sheetOpen = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: `true` quando há um filtro de categoria ativo — usado
   * pro badge de contagem do botão "Filtro" no cabeçalho (o período
   * não conta, sempre tem um valor).
   */
  protected readonly activeFilterCount = computed(() => (this.draftCategoryId() ? 1 : 0));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Abre o bottom sheet de filtro — chamado pelo botão
   * "Filtro" do cabeçalho da página (mobile).
   */
  openFilterSheet(): void {
    this.sheetOpen.set(true);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Carrega resumo/ranking/tabela do intervalo default ao
   * abrir a tela.
   */
  ngOnInit(): void {
    this.state.loadReports();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Atualiza o rascunho local do intervalo De/Até e já
   * propaga pro `ReportsStateService` na hora (mesmo padrão de
   * "período sempre instantâneo" de `TransactionFilterBarComponent` —
   * setas/`p-datepicker` filtram direto, sem exigir um clique extra em
   * "Aplicar"). Corrigido em 2026-08-15: antes só atualizava o
   * rascunho local, e como "Aplicar" só existe dentro do bottom sheet
   * mobile (filtro de categoria), mudar De/Até na tela principal não
   * filtrava nada — bug real reportado pelo usuário ("o filtro de
   * até... não está filtrando"). Usa o filtro de categoria já
   * *aplicado* (`state.filters().categoryId`), não o rascunho ainda
   * não confirmado (`draftCategoryId`) — evita aplicar de propósito
   * uma categoria que o usuário só tinha escolhido no sheet sem clicar
   * "Aplicar" ainda.
   */
  onDraftRangeChange(range: ReportsDateRange): void {
    this.draftRange.set(range);
    this.state.applyPeriodRangeAndFilters(range, { categoryId: this.state.filters().categoryId });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Botão "Aplicar" — propaga o rascunho (intervalo +
   * categoria) pro `ReportsStateService`, que recarrega tudo. Fecha o
   * sheet mobile também (inofensivo no desktop, onde nunca abre).
   */
  apply(): void {
    this.state.applyPeriodRangeAndFilters(this.draftRange(), {
      categoryId: this.draftCategoryId(),
    });
    this.sheetOpen.set(false);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Botão "Limpar" — volta o estado compartilhado ao padrão
   * e sincroniza o rascunho local com o resultado. Fecha o sheet mobile
   * também.
   */
  clear(): void {
    this.state.resetFilters();
    this.draftRange.set(this.state.periodRange());
    this.draftCategoryId.set('');
    this.sheetOpen.set(false);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Navega para outra página da tabela.
   */
  goToPage(page: number): void {
    this.state.goToPage(page);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Dispara o download do CSV do filtro atual.
   */
  exportCsv(): void {
    this.state.exportCsv();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Botão "Gerar análise" do `ai-narrative-card`.
   */
  generateNarrative(): void {
    this.state.generateNarrative();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Botão "Tentar novamente" do estado de erro — recarrega
   * resumo/ranking/tabela do filtro atual.
   */
  retry(): void {
    this.state.loadReports();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Total de despesas dividido pelo número de meses do
   * intervalo selecionado (build-context-05 §3.4).
   */
  protected readonly averageMonthly = computed(() => {
    const summary = this.state.summary();
    if (!summary) {
      return '0';
    }
    const months = Math.max(1, monthsBetween(this.state.periodRange().dateFrom, this.state.periodRange().dateTo));
    return (Number(summary.total_expense) / months).toFixed(2);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Rótulo "AAAA-MM – AAAA-MM" do intervalo atual — usado no
   * subtítulo do `ai-narrative-card`.
   */
  protected readonly periodLabel = computed(() => {
    const range = this.state.periodRange();
    return `${range.dateFrom.slice(0, 7)} – ${range.dateTo.slice(0, 7)}`;
  });
}
