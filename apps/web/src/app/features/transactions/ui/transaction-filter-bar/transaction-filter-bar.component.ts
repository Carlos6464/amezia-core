import { Component, computed, inject, input, model, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { DatePickerModule } from 'primeng/datepicker';
import type { PaymentStatus } from '@amezia/shared-types';

import { BreakpointService } from '../../../../core/viewport/breakpoint.service';
import {
  DropdownSelectComponent,
  type DropdownSelectOption,
} from '../../../../shared/ui/dropdown-select/dropdown-select.component';

const INTL_LOCALE_BY_LANG: Record<string, string> = { 'pt-BR': 'pt-BR', en: 'en-US' };

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Busca + navegador de período (mês/ano) + filtro de status
 * + Buscar/Limpar — mapeia `expenses/index.html` (`comp-filter-bar`).
 * Sem filtro de tipo: produto é expense-only (2026-08-14). Diferente do
 * módulo Categorias, aqui cada busca é uma requisição ao backend (RN-05
 * — description criptografado exige busca em memória no servidor),
 * então `q`/`status` só são aplicados quando o usuário clica "Buscar",
 * não a cada tecla digitada. Navegação de período (setas) é instantânea.
 * No mobile (ajuste de 2026-08-09), a barra inline vira um único botão
 * "Filtro" — os mesmos campos (busca, período, status) se mudam para
 * dentro de um bottom sheet que sobe da parte de baixo da tela, estilo
 * app nativo,
 * ocupando a tela inteira — o botão que abre esse sheet fica no
 * cabeçalho da página (fora deste componente, ver `TransactionListComponent`),
 * então este componente expõe `openSheet()`/`activeFilterCount` como API
 * pública em vez de desenhar o próprio gatilho.
 */
@Component({
  selector: 'app-transaction-filter-bar',
  standalone: true,
  imports: [FormsModule, TranslocoModule, DropdownSelectComponent, DatePickerModule],
  templateUrl: './transaction-filter-bar.component.html',
  styleUrl: './transaction-filter-bar.component.css',
})
export class TransactionFilterBarComponent {
  private readonly transloco = inject(TranslocoService);
  protected readonly breakpoint = inject(BreakpointService);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Opções do dropdown de status.
   */
  protected readonly statusOptions: DropdownSelectOption[] = [
    { value: '', labelKey: 'transactions.filterBar.allStatuses' },
    { value: 'pending', labelKey: 'transactions.status.pending' },
    { value: 'paid', labelKey: 'transactions.status.paid' },
  ];

  year = input.required<number>();
  month = input.required<number>();

  q = model('');
  status = model<PaymentStatus | ''>('');

  // "search" é nome de evento DOM nativo (dispara em <input type="search">) —
  // @angular-eslint/no-output-native não deixa reusar o nome num @Output().
  searchRequested = output<void>();
  clear = output<void>();
  periodChange = output<{ year: number; month: number }>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Controla a visibilidade do bottom sheet mobile — pública
   * (via `openSheet()`) porque quem aciona a abertura é o botão no
   * cabeçalho da página, fora deste componente. A barra inline
   * (desktop) não usa esse estado.
   */
  protected readonly sheetOpen = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Abre o bottom sheet — chamado de fora (botão de filtro no
   * cabeçalho da página, via `@ViewChild`).
   */
  openSheet(): void {
    this.sheetOpen.set(true);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Quantos filtros estão ativos além do período (que sempre
   * tem um valor) — lido de fora pelo botão de filtro no cabeçalho da
   * página, pra mostrar um badge de contagem sem precisar abrir o sheet.
   */
  readonly activeFilterCount = computed(() => {
    let count = 0;
    if (this.q().trim() !== '') count++;
    if (this.status() !== '') count++;
    return count;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Rótulo "Agosto 2026" formatado no idioma ativo do
   * Transloco — evita precisar de 12 chaves de i18n só para nomes de mês.
   */
  readonly monthLabel = computed(() => {
    const locale = INTL_LOCALE_BY_LANG[this.transloco.getActiveLang()] ?? 'pt-BR';
    const date = new Date(this.year(), this.month() - 1, 1);
    const formatted = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(
      date,
    );
    return formatted.charAt(0).toUpperCase() + formatted.slice(1);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Data (1º dia do mês) representando `year`/`month` —
   * valor do `p-datepicker`, permitindo selecionar o período direto no
   * calendário em vez de só navegar mês a mês pelas setas (pedido do
   * usuário em 2026-08-15, mesmo padrão de `PeriodPickerComponent` do
   * Dashboard).
   */
  readonly selectedDate = computed(() => new Date(this.year(), this.month() - 1, 1));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Navega para o mês anterior, virando o ano quando
   * necessário (janeiro → dezembro do ano anterior).
   */
  previousMonth(): void {
    const month = this.month() === 1 ? 12 : this.month() - 1;
    const year = this.month() === 1 ? this.year() - 1 : this.year();
    this.periodChange.emit({ year, month });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Navega para o próximo mês, virando o ano quando
   * necessário (dezembro → janeiro do ano seguinte).
   */
  nextMonth(): void {
    const month = this.month() === 12 ? 1 : this.month() + 1;
    const year = this.month() === 12 ? this.year() + 1 : this.year();
    this.periodChange.emit({ year, month });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Handler do `p-datepicker` — emite o período escolhido
   * direto no calendário (`view="month"`), instantâneo como as setas
   * (ignora valores inválidos).
   */
  onDatePickerChange(value: Date | null): void {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) {
      return;
    }
    this.periodChange.emit({ year: value.getFullYear(), month: value.getMonth() + 1 });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Zera busca e filtros de tipo/status — o período
   * corrente não é afetado (a spec só fala em "sem busca" pro clear).
   */
  clearFilters(): void {
    this.q.set('');
    this.status.set('');
    this.clear.emit();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Aplica os filtros do bottom sheet mobile (mesmo evento
   * `searchRequested` do botão "Buscar" da barra desktop) e fecha o
   * sheet — o usuário já viu o efeito, não precisa fechar manualmente.
   */
  applyFromSheet(): void {
    this.searchRequested.emit();
    this.sheetOpen.set(false);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Limpa os filtros a partir do bottom sheet mobile e fecha
   * o sheet.
   */
  clearFromSheet(): void {
    this.clearFilters();
    this.sheetOpen.set(false);
  }
}
