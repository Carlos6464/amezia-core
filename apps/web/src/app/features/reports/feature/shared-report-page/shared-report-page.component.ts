import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import type {
  Category,
  CategoryDistributionItem,
  FinancialSummary,
  PaginatedTransactionsResponse,
} from '@amezia/shared-types';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { CategoryDistributionListComponent } from '../../ui/category-distribution-list/category-distribution-list.component';
import { MetricCardComponent } from '../../ui/metric-card/metric-card.component';
import { PeriodRangePickerComponent } from '../../ui/period-range-picker/period-range-picker.component';
import { TransactionsTableComponent } from '../../ui/transactions-table/transactions-table.component';
import { SharedReportApiService } from './shared-report-api.service';

const PAGE_SIZE = 15;

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function lastDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-18
 * Descrição: Últimos 6 meses corridos — mesmo intervalo default da
 * tela `/reports` do app, calculado aqui de novo (função pura, ~5
 * linhas) em vez de importado de `ReportsStateService`: essa tela é
 * pra ser genuinamente independente do sistema autenticado, então nem
 * uma função utilitária vem de um arquivo que pertence a ele.
 */
function defaultRange(): { dateFrom: string; dateTo: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() - 5, 1);
  return {
    dateFrom: `${start.getFullYear()}-${pad2(start.getMonth() + 1)}-01`,
    dateTo: `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(lastDayOfMonth(now.getFullYear(), now.getMonth() + 1))}`,
  };
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-18
 * Descrição: Página pública do link mágico do bot do WhatsApp (modo
 * Relatório) — `/reports/shared?token=...`, fora do
 * `AppShellComponent`/`authGuard`. Reescrita do zero (2026-08-18,
 * pedido do usuário): a 1ª versão reaproveitava o `ReportsPageComponent`
 * real do app (mesmos `ReportsStateService`/`AuthService` por trás) e
 * foi rejeitada — mesmo sem link nenhum de volta visível, tecnicamente
 * ainda era "o mesmo código do sistema". Esta versão usa a tela
 * `/reports` só como **referência visual** (reaproveita as 3 peças de
 * UI puras — `MetricCardComponent`/`CategoryDistributionListComponent`/
 * `TransactionsTableComponent`/`PeriodRangePickerComponent`, nenhuma
 * delas injeta serviço nenhum do sistema — e o CSS de
 * `reports-design.css`) mas tem seu próprio estado local e seu próprio
 * cliente HTTP (`SharedReportApiService`), sem tocar em
 * `AuthService`/`ReportsStateService`/`CategoriesService`.
 */
@Component({
  selector: 'app-shared-report-page',
  standalone: true,
  imports: [
    FormsModule,
    TranslocoModule,
    BrlAmountPipe,
    MetricCardComponent,
    PeriodRangePickerComponent,
    CategoryDistributionListComponent,
    TransactionsTableComponent,
  ],
  templateUrl: './shared-report-page.component.html',
  styleUrl: './shared-report-page.component.css',
})
export class SharedReportPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(SharedReportApiService);

  protected readonly tokenMissing = signal(false);
  private token = '';

  protected readonly periodRange = signal(defaultRange());
  protected readonly categoryId = signal('');
  protected readonly categories = signal<Category[]>([]);
  protected readonly page = signal(1);

  protected readonly summary = signal<FinancialSummary | null>(null);
  protected readonly distribution = signal<CategoryDistributionItem[]>([]);
  protected readonly transactionsPage = signal<PaginatedTransactionsResponse | null>(null);

  protected readonly loading = signal(false);
  protected readonly error = signal(false);
  protected readonly exportLoading = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: "AAAA-MM – AAAA-MM" do intervalo atual, mesmo rótulo da
   * tela `/reports` de verdade.
   */
  protected readonly periodLabel = computed(() => {
    const range = this.periodRange();
    return `${range.dateFrom.slice(0, 7)} – ${range.dateTo.slice(0, 7)}`;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Lê `?token=` da URL — sem token, nem tenta chamar a API
   * (mostra o estado de link inválido). Com token, carrega categorias
   * (pro filtro) + os dados do intervalo default.
   */
  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.tokenMissing.set(true);
      return;
    }
    this.token = token;
    this.api.listCategories(this.token).subscribe({
      next: (categories) => this.categories.set(categories),
      error: () => undefined,
    });
    this.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Parâmetros atuais (intervalo + filtro de categoria)
   * reaproveitados por `load()`/`loadTransactions()`/`exportCsv()`.
   */
  private currentParams() {
    const range = this.periodRange();
    return { dateFrom: range.dateFrom, dateTo: range.dateTo, categoryId: this.categoryId() || undefined };
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Recarrega resumo + ranking + tabela do intervalo/filtro
   * atuais — chamado ao entrar na tela, ao trocar período/categoria e
   * pelo botão "Tentar novamente".
   */
  protected load(): void {
    this.loading.set(true);
    this.error.set(false);

    const params = this.currentParams();
    this.api.getSummary(this.token, params).subscribe({
      next: (summary) => {
        this.summary.set(summary);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.error.set(true);
      },
    });
    this.api.getCategoryDistribution(this.token, params).subscribe({
      next: (items) => this.distribution.set(items),
      error: () => this.error.set(true),
    });
    this.loadTransactions();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Recarrega só a tabela paginada — usado por `load()` e
   * por `goToPage()` (trocar de página não precisa recalcular resumo
   * nem ranking, só a página atual da tabela).
   */
  private loadTransactions(): void {
    this.api.getTransactions(this.token, this.currentParams(), this.page(), PAGE_SIZE).subscribe({
      next: (result) => this.transactionsPage.set(result),
      error: () => this.error.set(true),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Troca de intervalo De/Até — aplica na hora (mesmo padrão
   * "período sempre instantâneo" do resto do app), volta pra página 1.
   */
  protected onRangeChange(range: { dateFrom: string; dateTo: string }): void {
    this.periodRange.set(range);
    this.page.set(1);
    this.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Troca do filtro de categoria (`<select>` nativo, não o
   * `app-report-category-select` do app — esse injeta `CategoriesService`,
   * exatamente a dependência que esta tela evita).
   */
  protected onCategoryChange(categoryId: string): void {
    this.categoryId.set(categoryId);
    this.page.set(1);
    this.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Navega pra outra página da tabela, mantendo período/
   * categoria atuais — `(pageChange)` de `TransactionsTableComponent`.
   */
  protected goToPage(page: number): void {
    this.page.set(page);
    this.loadTransactions();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Baixa o CSV do filtro atual — mesmo mecanismo de
   * `ReportsStateService.exportCsv` (link temporário +
   * `URL.createObjectURL`), reimplementado aqui pra não importar nada
   * do módulo de dados do sistema.
   */
  protected exportCsv(): void {
    this.exportLoading.set(true);
    this.api.exportCsv(this.token, this.currentParams()).subscribe({
      next: (response) => {
        this.exportLoading.set(false);
        const blob = response.body;
        if (!blob) {
          return;
        }
        const match = response.headers.get('content-disposition')?.match(/filename="?([^"]+)"?/);
        const filename = match?.[1] ?? 'relatorio.csv';
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
      },
      error: () => {
        this.exportLoading.set(false);
        this.error.set(true);
      },
    });
  }
}
