import { Component, computed, inject, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { DatePickerModule } from 'primeng/datepicker';

const INTL_LOCALE_BY_LANG: Record<string, string> = { 'pt-BR': 'pt-BR', en: 'en-US' };

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Navegador de período de um mês só (Dashboard, `/dashboard`)
 * — setas anterior/próximo + atalhos -1 ano / atual / +1 ano + seleção
 * direta do mês/ano via `p-datepicker` (`view="month"`), mapeando
 * `screem/dashboard/index.html` (`.period-wrap`, build-context-05
 * §3.3) com o ajuste pedido pelo usuário em 2026-08-14 (ver DIARIO.md):
 * antes só dava pra navegar mês a mês pelas setas, agora também dá pra
 * abrir o calendário e escolher o período direto — mesmo padrão do
 * irmão em `/home/adriano/Documentos/projetos/Amezia`.
 */
@Component({
  selector: 'app-period-picker',
  standalone: true,
  imports: [TranslocoModule, FormsModule, DatePickerModule],
  templateUrl: './period-picker.component.html',
  styleUrl: './period-picker.component.css',
})
export class PeriodPickerComponent {
  private readonly transloco = inject(TranslocoService);

  year = input.required<number>();
  month = input.required<number>();

  periodChange = output<{ year: number; month: number }>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Rótulo "Junho de 2026" no idioma ativo — mesmo padrão de
   * `TransactionFilterBarComponent.monthLabel`.
   */
  readonly monthLabel = computed(() => {
    const locale = INTL_LOCALE_BY_LANG[this.transloco.getActiveLang()] ?? 'pt-BR';
    const date = new Date(this.year(), this.month() - 1, 1);
    const formatted = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(date);
    return formatted.charAt(0).toUpperCase() + formatted.slice(1);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `true` quando o período exibido é o atalho "Atual" — só
   * pra destacar o pill correspondente.
   */
  readonly isCurrent = computed(() => {
    const now = new Date();
    return this.year() === now.getFullYear() && this.month() === now.getMonth() + 1;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Data (1º dia do mês) representando `year`/`month` —
   * valor do `p-datepicker`, permitindo selecionar o período direto no
   * calendário em vez de só navegar mês a mês pelas setas.
   */
  readonly selectedDate = computed(() => new Date(this.year(), this.month() - 1, 1));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Navega para o mês anterior, virando o ano quando
   * necessário.
   */
  previousMonth(): void {
    const month = this.month() === 1 ? 12 : this.month() - 1;
    const year = this.month() === 1 ? this.year() - 1 : this.year();
    this.periodChange.emit({ year, month });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Navega para o próximo mês, virando o ano quando
   * necessário.
   */
  nextMonth(): void {
    const month = this.month() === 12 ? 1 : this.month() + 1;
    const year = this.month() === 12 ? this.year() + 1 : this.year();
    this.periodChange.emit({ year, month });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Atalhos "-1 ano"/"Atual"/"+1 ano" — mantêm o mesmo mês,
   * só trocam o ano em relação ao ano corrente (não ao ano exibido).
   */
  goToShortcut(offsetYears: number): void {
    const now = new Date();
    this.periodChange.emit({ year: now.getFullYear() + offsetYears, month: now.getMonth() + 1 });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Handler do `p-datepicker` — emite o período escolhido
   * direto no calendário (`view="month"`), ignorando valores inválidos.
   */
  onDatePickerChange(value: Date | null): void {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) {
      return;
    }
    this.periodChange.emit({ year: value.getFullYear(), month: value.getMonth() + 1 });
  }
}
