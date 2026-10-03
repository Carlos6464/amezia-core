import type { AbstractControl, ValidationErrors } from '@angular/forms';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-18
 * Descrição: Formata dígitos de telefone como `+55 (11) 99999-0001`
 * progressivamente, conforme o usuário digita — os 2 primeiros dígitos
 * são o código do país (`+55`), sempre presente na máscara. Assume
 * número brasileiro (DDD de 2 dígitos + 9 dígitos de assinante); um
 * `phone` salvo antes desta máscara existir, sem o prefixo `55`, pode
 * exibir errado na 1ª carga — limitação aceita, não há como distinguir
 * formatos antigos de forma confiável. Extraído de `ProfilePageComponent`
 * (2026-08-16) para ser reaproveitado pelo modal de configuração rápida
 * do Dashboard, que edita o mesmo campo.
 */
export function formatPhoneDigits(digits: string): string {
  if (!digits) {
    return '';
  }
  const country = digits.slice(0, 2);
  const area = digits.slice(2, 4);
  const rest = digits.slice(4, 13);

  let result = `+${country}`;
  if (area) {
    result += ` (${area}`;
    if (area.length === 2) {
      result += ')';
    }
  }
  if (rest) {
    result += ` ${rest.slice(0, 5)}`;
    if (rest.length > 5) {
      result += `-${rest.slice(5, 9)}`;
    }
  }
  return result;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-18
 * Descrição: Remove a máscara visual antes de enviar ao backend — o
 * valor salvo é só `+` seguido dos dígitos (ex.: `+5511999990001`), sem
 * parênteses/espaço/traço. `null` quando o campo está vazio, para quem
 * chama omitir `phone` do payload em vez de mandar uma string vazia
 * (que o backend trataria como "definir telefone vazio", não como "não
 * mexer no campo").
 */
export function normalizePhoneForSubmit(value: string): string | null {
  const digits = value.replace(/\D/g, '');
  return digits ? `+${digits}` : null;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-19
 * Descrição: `true` quando os dígitos formam um telefone completo pro
 * formato que `formatPhoneDigits` monta (2 DDI + 2 DDD + 9 assinante =
 * 13 dígitos) — campo vazio também conta como "completo" porque o
 * telefone é opcional, só um valor parcial (ex.: só o DDI digitado) é
 * inválido. Checagem só de tamanho, feita no cliente pra dar feedback
 * imediato; a validação de verdade (DDD/faixa reais por país, via
 * `phonenumbers`) acontece no backend (`UpdateProfileRequest.validate_phone`).
 */
export function isPhoneComplete(digits: string): boolean {
  return digits.length === 0 || digits.length === 13;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-19
 * Descrição: Validator de `FormControl` para o campo de telefone —
 * wrapper de `isPhoneComplete` sobre o valor mascarado do controle,
 * pro `ProfilePageComponent` (`personalInfoForm`) barrar o salvamento
 * de um número incompleto sem precisar reimplementar a checagem.
 */
export function phoneCompleteValidator(control: AbstractControl): ValidationErrors | null {
  const digits = (control.value ?? '').replace(/\D/g, '');
  return isPhoneComplete(digits) ? null : { phoneIncomplete: true };
}
