import { Component, computed, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { PaginatedTransactionsResponse } from '@amezia/shared-types';

import { BrDatePipe } from '../../../../shared/pipes/br-date.pipe';
import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';

const MAX_VISIBLE_PAGES = 5;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Tabela paginada de transações da tela de Reports
 * (build-context-05 §3.4) — desktop em `<table>`, mobile em cards
 * (`.dt-card-list`, mesmo breakpoint 700px do resto do app). Somente
 * leitura: sem ações de editar/excluir/pagar (isso é responsabilidade
 * do módulo de Transações, não de Relatórios).
 */
@Component({
  selector: 'app-transactions-table',
  standalone: true,
  imports: [TranslocoModule, BrDatePipe, BrlAmountPipe],
  templateUrl: './transactions-table.component.html',
  styleUrl: './transactions-table.component.css',
})
export class TransactionsTableComponent {
  page = input<PaginatedTransactionsResponse | null>(null);
  loading = input(false);

  pageChange = output<number>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Índice (1-based) do primeiro item exibido na página
   * atual — usado no texto "Mostrando X–Y de Z".
   */
  protected readonly showingFrom = computed(() => {
    const pagination = this.page()?.pagination;
    if (!pagination || pagination.total === 0) {
      return 0;
    }
    return (pagination.page - 1) * pagination.page_size + 1;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Índice (1-based) do último item exibido na página
   * atual — nunca ultrapassa `total`.
   */
  protected readonly showingTo = computed(() => {
    const pagination = this.page()?.pagination;
    if (!pagination) {
      return 0;
    }
    return Math.min(pagination.page * pagination.page_size, pagination.total);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Janela de números de página exibida na paginação (até
   * `MAX_VISIBLE_PAGES`, centrada na página atual) — mapeia os botões
   * numerados do protótipo `screem/reports/index.html`.
   */
  protected readonly pageNumbers = computed<number[]>(() => {
    const pagination = this.page()?.pagination;
    if (!pagination || pagination.total_pages <= 1) {
      return pagination ? [1] : [];
    }
    const total = pagination.total_pages;
    const current = pagination.page;
    const half = Math.floor(MAX_VISIBLE_PAGES / 2);
    let start = Math.max(1, current - half);
    const end = Math.min(total, start + MAX_VISIBLE_PAGES - 1);
    start = Math.max(1, end - MAX_VISIBLE_PAGES + 1);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  });
}
