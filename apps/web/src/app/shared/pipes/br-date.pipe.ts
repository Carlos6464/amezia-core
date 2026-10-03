import { Pipe, PipeTransform } from '@angular/core';

const BR_DATE_FORMATTER = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});

const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})/;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-11
 * Descrição: Pipe de exibição pra qualquer data do app — formata uma
 * string `YYYY-MM-DD` (formato que a API sempre manda, serialização
 * padrão do `datetime.date` do Pydantic) pro formato brasileiro
 * `DD/MM/AAAA`. Mesmo espírito de `BrlAmountPipe`: usa `Intl` nativo,
 * sem depender de `registerLocaleData`/`LOCALE_ID` do Angular.
 */
@Pipe({
  name: 'brDate',
  standalone: true,
})
export class BrDatePipe implements PipeTransform {
  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Faz o parse manual dos componentes ano/mês/dia e monta
   * um `Date` em horário local (`new Date(ano, mês, dia)`), nunca via
   * `new Date(string)` — esse construtor interpreta `"YYYY-MM-DD"` como
   * meia-noite UTC, que em qualquer fuso horário atrás de UTC (Brasil
   * inteiro) exibe o dia anterior ao correto. Valor que não bate com o
   * formato esperado volta cru, sem lançar erro.
   */
  transform(value: string | null | undefined): string {
    if (!value) {
      return '';
    }
    const match = ISO_DATE_PATTERN.exec(value);
    if (!match) {
      return value;
    }
    const [, year, month, day] = match;
    const date = new Date(Number(year), Number(month) - 1, Number(day));
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return BR_DATE_FORMATTER.format(date);
  }
}
