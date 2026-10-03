import { Component, computed, inject, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { DatePickerModule } from 'primeng/datepicker';

const INTL_LOCALE_BY_LANG: Record<string, string> = { 'pt-BR': 'pt-BR', en: 'en-US' };

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function lastDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function parseYearMonth(isoDate: string): { year: number; month: number } {
  const [year, month] = isoDate.split('-').map(Number);
  return { year, month };
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Navegador de intervalo De/Até (mês/ano cada, tela
 * `/reports`) — mapeia `screem/reports/index.html`
 * (`.comp-fb-period-range`, build-context-05 §3.4). `dateFrom`/`dateTo`
 * são sempre o 1º e o último dia do mês respectivamente — o
 * componente nunca deixa escolher um dia específico. Além das setas
 * anterior/próximo, cada lado (`De`/`Até`) também tem um
 * `p-datepicker` (`view="month"`) pra selecionar o mês/ano direto no
 * calendário — pedido do usuário em 2026-08-14 (ver DIARIO.md), mesmo
 * padrão do irmão em `/home/adriano/Documentos/projetos/Amezia`.
 */
@Component({
  selector: 'app-period-range-picker',
  standalone: true,
  imports: [TranslocoModule, FormsModule, DatePickerModule],
  templateUrl: './period-range-picker.component.html',
  styleUrl: './period-range-picker.component.css',
})
export class PeriodRangePickerComponent {
  private readonly transloco = inject(TranslocoService);

  dateFrom = input.required<string>();
  dateTo = input.required<string>();

  rangeChange = output<{ dateFrom: string; dateTo: string }>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Componentes ano/mês parseados de `dateFrom()`.
   */
  private readonly fromParts = computed(() => parseYearMonth(this.dateFrom()));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Componentes ano/mês parseados de `dateTo()`.
   */
  private readonly toParts = computed(() => parseYearMonth(this.dateTo()));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Rótulo "MM/AAAA" de `De`, no idioma ativo.
   */
  readonly fromLabel = computed(() => this.monthLabel(this.fromParts()));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Rótulo "MM/AAAA" de `Até`, no idioma ativo.
   */
  readonly toLabel = computed(() => this.monthLabel(this.toParts()));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `Date` (1º dia do mês) de `dateFrom()` — valor do
   * `p-datepicker` do lado "De".
   */
  readonly fromDate = computed(() => {
    const parts = this.fromParts();
    return new Date(parts.year, parts.month - 1, 1);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `Date` (1º dia do mês) de `dateTo()` — valor do
   * `p-datepicker` do lado "Até".
   */
  readonly toDate = computed(() => {
    const parts = this.toParts();
    return new Date(parts.year, parts.month - 1, 1);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Rótulo "MM/AAAA" no idioma ativo, para um par ano/mês.
   */
  private monthLabel(parts: { year: number; month: number }): string {
    const locale = INTL_LOCALE_BY_LANG[this.transloco.getActiveLang()] ?? 'pt-BR';
    const date = new Date(parts.year, parts.month - 1, 1);
    return new Intl.DateTimeFormat(locale, { month: '2-digit', year: 'numeric' }).format(date);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Emite o novo intervalo como `dateFrom`/`dateTo` ISO —
   * `from` sempre no 1º dia do mês, `to` sempre no último.
   */
  private emitRange(from: { year: number; month: number }, to: { year: number; month: number }): void {
    this.rangeChange.emit({
      dateFrom: `${from.year}-${pad2(from.month)}-01`,
      dateTo: `${to.year}-${pad2(to.month)}-${pad2(lastDayOfMonth(to.year, to.month))}`,
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Navega o mês de início (`De`) para trás/frente — não
   * deixa `De` ficar depois de `Até`, empurrando `Até` junto quando
   * necessário.
   */
  moveFrom(delta: number): void {
    const from = this.addMonths(this.fromParts(), delta);
    const to = this.toParts();
    const clampedTo = this.isAfter(from, to) ? from : to;
    this.emitRange(from, clampedTo);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Navega o mês de fim (`Até`) para trás/frente — não deixa
   * `Até` ficar antes de `De`, empurrando `De` junto quando necessário.
   */
  moveTo(delta: number): void {
    const to = this.addMonths(this.toParts(), delta);
    const from = this.fromParts();
    const clampedFrom = this.isAfter(from, to) ? to : from;
    this.emitRange(clampedFrom, to);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Handler do `p-datepicker` do lado "De" — seleciona o mês
   * direto no calendário, empurrando `Até` junto quando `De` passaria a
   * ficar depois dele (mesma regra de `moveFrom`).
   */
  onFromDatePickerChange(value: Date | null): void {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) {
      return;
    }
    const from = { year: value.getFullYear(), month: value.getMonth() + 1 };
    const to = this.toParts();
    const clampedTo = this.isAfter(from, to) ? from : to;
    this.emitRange(from, clampedTo);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Handler do `p-datepicker` do lado "Até" — seleciona o mês
   * direto no calendário, empurrando `De` junto quando `Até` passaria a
   * ficar antes dele (mesma regra de `moveTo`).
   */
  onToDatePickerChange(value: Date | null): void {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) {
      return;
    }
    const to = { year: value.getFullYear(), month: value.getMonth() + 1 };
    const from = this.fromParts();
    const clampedFrom = this.isAfter(from, to) ? to : from;
    this.emitRange(clampedFrom, to);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Soma (ou subtrai) `delta` meses a um par ano/mês,
   * virando o ano quando necessário.
   */
  private addMonths(
    parts: { year: number; month: number },
    delta: number,
  ): { year: number; month: number } {
    const totalMonths = parts.year * 12 + (parts.month - 1) + delta;
    return { year: Math.floor(totalMonths / 12), month: (totalMonths % 12) + 1 };
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `true` se `a` é um mês posterior a `b` — usado para
   * impedir que `De` fique depois de `Até` (e vice-versa).
   */
  private isAfter(a: { year: number; month: number }, b: { year: number; month: number }): boolean {
    return a.year * 12 + a.month > b.year * 12 + b.month;
  }
}
