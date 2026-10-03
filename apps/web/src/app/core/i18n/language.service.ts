import { Injectable, inject } from '@angular/core';
import { TranslocoService } from '@jsverse/transloco';
import { PrimeNG } from 'primeng/config';

const AVAILABLE_LANGS = ['pt-BR', 'en'];
const DEFAULT_LANG = 'pt-BR';

const PT_BR_MONTH_NAMES = [
  'Janeiro',
  'Fevereiro',
  'Março',
  'Abril',
  'Maio',
  'Junho',
  'Julho',
  'Agosto',
  'Setembro',
  'Outubro',
  'Novembro',
  'Dezembro',
];
const PT_BR_MONTH_NAMES_SHORT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const PT_BR_DAY_NAMES = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
const PT_BR_DAY_NAMES_SHORT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
const PT_BR_DAY_NAMES_MIN = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];

const EN_MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];
const EN_MONTH_NAMES_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const EN_DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const EN_DAY_NAMES_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const EN_DAY_NAMES_MIN = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Nomes de mês/dia (calendário/`p-datepicker` do PrimeNG,
 * que tem o próprio sistema de tradução independente do Transloco) no
 * idioma informado — sem isso o `p-datepicker` do período (Dashboard/
 * Reports, adicionado em 2026-08-14) mostrava "Jan Feb Mar..." mesmo
 * com o app inteiro em pt-BR.
 */
function primeNgTranslationFor(lang: string): {
  monthNames: string[];
  monthNamesShort: string[];
  dayNames: string[];
  dayNamesShort: string[];
  dayNamesMin: string[];
  firstDayOfWeek: number;
  today: string;
} {
  if (lang === 'pt-BR') {
    return {
      monthNames: PT_BR_MONTH_NAMES,
      monthNamesShort: PT_BR_MONTH_NAMES_SHORT,
      dayNames: PT_BR_DAY_NAMES,
      dayNamesShort: PT_BR_DAY_NAMES_SHORT,
      dayNamesMin: PT_BR_DAY_NAMES_MIN,
      firstDayOfWeek: 0,
      today: 'Hoje',
    };
  }
  return {
    monthNames: EN_MONTH_NAMES,
    monthNamesShort: EN_MONTH_NAMES_SHORT,
    dayNames: EN_DAY_NAMES,
    dayNamesShort: EN_DAY_NAMES_SHORT,
    dayNamesMin: EN_DAY_NAMES_MIN,
    firstDayOfWeek: 0,
    today: 'Today',
  };
}

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private readonly transloco = inject(TranslocoService);
  private readonly primeNg = inject(PrimeNG);

  constructor() {
    this.transloco.langChanges$.subscribe((lang) => this.primeNg.setTranslation(primeNgTranslationFor(lang)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-06
   * Descrição: Define o idioma ativo a partir do idioma do navegador como
   * fallback. Assim que o login existir (build-context-01), a preferência
   * `language` do perfil do usuário passa a ter prioridade sobre isso.
   */
  initFromBrowser(): void {
    const browserLang = navigator.language;
    const matched = AVAILABLE_LANGS.find((lang) => browserLang.startsWith(lang.slice(0, 2)));
    this.transloco.setActiveLang(matched ?? DEFAULT_LANG);
  }

  setLanguage(lang: string): void {
    if (AVAILABLE_LANGS.includes(lang)) {
      this.transloco.setActiveLang(lang);
    }
  }
}
