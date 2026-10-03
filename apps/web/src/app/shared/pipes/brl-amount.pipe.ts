import { Pipe, PipeTransform } from '@angular/core';

const BRL_FORMATTER = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-11
 * Descrição: Pipe de exibição pra qualquer valor monetário do app — o
 * PRD/CLAUDE.md não preveem conversão multi-moeda no MVP1, então é só
 * Real por enquanto, sem símbolo de moeda (o "R$" fica pra quando isso
 * mudar). Usado em qualquer tela que mostra dinheiro: tabela/cards de
 * transação, cards de resumo, preview em tempo real do formulário.
 */
@Pipe({
  name: 'brlAmount',
  standalone: true,
})
export class BrlAmountPipe implements PipeTransform {
  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Formata um valor monetário (string decimal vinda da API,
   * ex.: `"1200.00"`, ou texto que o usuário está digitando num campo)
   * pro formato brasileiro — vírgula decimal, ponto de milhar
   * (`"1.200,00"`). `Intl.NumberFormat` é API nativa do navegador — não
   * depende de registrar locale do Angular (`registerLocaleData`/
   * `LOCALE_ID`), que só é exigido pelos pipes `DecimalPipe`/
   * `CurrencyPipe` embutidos, não usados aqui. Nunca lança erro: um
   * valor que ainda não dá pra interpretar como número (campo vazio,
   * usuário no meio de digitar "43,") volta cru, sem formatar, em vez
   * de quebrar a tela.
   */
  transform(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === '') {
      return '';
    }
    const normalized = typeof value === 'string' ? value.replace(',', '.') : value;
    const parsed = typeof normalized === 'number' ? normalized : Number(normalized);
    if (!Number.isFinite(parsed)) {
      return String(value);
    }
    return BRL_FORMATTER.format(parsed);
  }
}
