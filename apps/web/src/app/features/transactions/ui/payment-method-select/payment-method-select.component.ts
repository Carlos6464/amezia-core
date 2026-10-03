import {
  Component,
  ElementRef,
  HostListener,
  OnDestroy,
  computed,
  forwardRef,
  inject,
  signal,
} from '@angular/core';
import { ControlValueAccessor, FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';

import { PAYMENT_METHODS } from '../../data-access/payment-method.model';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-10
 * Descrição: Seletor pesquisável (combobox) do método de pagamento —
 * mesmo padrão visual/interação do `CategorySelectComponent`, mas com
 * uma lista fixa (sem serviço, sem criação inline, sem grupos). Integrado
 * a Reactive Forms via ControlValueAccessor.
 */
@Component({
  selector: 'app-payment-method-select',
  standalone: true,
  imports: [FormsModule, TranslocoModule],
  templateUrl: './payment-method-select.component.html',
  styleUrl: './payment-method-select.component.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PaymentMethodSelectComponent),
      multi: true,
    },
  ],
})
export class PaymentMethodSelectComponent implements ControlValueAccessor, OnDestroy {
  private readonly transloco = inject(TranslocoService);
  private readonly elementRef = inject(ElementRef<HTMLElement>);

  readonly methods = PAYMENT_METHODS;

  // Signal, não campo simples — mesmo motivo do CategorySelectComponent:
  // um `computed()` só reage a leituras de Signal.
  private readonly valueSignal = signal('');
  disabled = false;

  readonly open = signal(false);
  readonly searchTerm = signal('');

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Posição do `.cat-dropdown`, calculada a cada abertura
   * (`toggle`/`updateDropdownPosition`) — ver o método pra explicação
   * de por que isso existe (bug real: dropdown cortado dentro do
   * `p-dialog` "Marcar como pago").
   */
  readonly dropdownPosition = signal({ top: 0, left: 0, width: 0 });

  // eslint-disable-next-line @typescript-eslint/no-empty-function
  private onChange: (value: string) => void = () => {};
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  onTouched: () => void = () => {};

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Método atualmente selecionado (para o botão de gatilho) —
   * `undefined` quando nenhum foi escolhido.
   */
  readonly selectedMethod = computed(() =>
    this.methods.find((method) => method.value === this.valueSignal()),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Filtra a lista fixa pelo texto já traduzido (não pelo
   * `value` em inglês) — a busca precisa bater com o que o usuário está
   * vendo na tela, não com o código interno.
   */
  readonly filteredMethods = computed(() => {
    const term = this.searchTerm().trim().toLowerCase();
    if (!term) {
      return this.methods;
    }
    return this.methods.filter((method) =>
      this.transloco.translate(method.labelKey).toLowerCase().includes(term),
    );
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Hook do ControlValueAccessor — Angular chama isso para
   * escrever um valor no componente programaticamente (ex.: `form.reset()`
   * ou `patchValue()` ao pré-preencher a edição).
   */
  writeValue(value: string): void {
    this.valueSignal.set(value ?? '');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Hook do ControlValueAccessor — registra o callback que o
   * Angular usa para saber quando o valor mudou.
   */
  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Hook do ControlValueAccessor — registra o callback de
   * "touched", disparado quando o dropdown fecha.
   */
  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Hook do ControlValueAccessor — reflete `[disabled]` do
   * FormControl no botão de gatilho.
   */
  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Abre/fecha o dropdown — zera a busca e recalcula a
   * posição a cada abertura (`updateDropdownPosition`), e liga/desliga
   * o listener de scroll que fecha o dropdown se a posição calculada
   * ficar obsoleta (`_bindScrollClose`/`_unbindScrollClose`).
   */
  toggle(): void {
    if (this.disabled) {
      return;
    }
    this.open.update((current) => !current);
    if (this.open()) {
      this.searchTerm.set('');
      this.updateDropdownPosition();
      this._bindScrollClose();
    } else {
      this._unbindScrollClose();
      this.onTouched();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Calcula a posição do `.cat-dropdown` em `position: fixed`
   * — bug real reportado pelo usuário: dentro do modal "Marcar como
   * pago" (`p-dialog`), o dropdown (antes `position: absolute`) ficava
   * cortado pelo `overflow-y: auto` do `.p-dialog-content` do PrimeNG,
   * que passou a rolar internamente assim que este componente foi
   * adicionado ao modal (build-context-13, "forma de pagamento no modal
   * Pagar"). `position: fixed` escapa desse corte, mas só funciona
   * corretamente porque o `.p-dialog` do PrimeNG aplica `transform:
   * scale(1)` mesmo em repouso — isso o torna o "containing block" de
   * qualquer descendente `fixed` (regra do CSS), então o dropdown passa
   * a ser posicionado relativo ao `.p-dialog` (que não tem `overflow`
   * definido, logo não corta nada) em vez da viewport crua. Por isso as
   * coordenadas abaixo descontam o retângulo desse ancestral quando ele
   * existe; fora de um dialog (uso normal no formulário de transação),
   * não há ancestral transformado, e o cálculo cai pro mesmo valor que
   * `position: fixed` relativo à viewport já daria sozinho.
   */
  private updateDropdownPosition(): void {
    const trigger = this.elementRef.nativeElement.querySelector('.cat-select') as HTMLElement;
    const triggerRect = trigger.getBoundingClientRect();
    const dialogAncestor = trigger.closest('.p-dialog');
    const originRect = dialogAncestor?.getBoundingClientRect();
    this.dropdownPosition.set({
      top: triggerRect.bottom - (originRect?.top ?? 0) + 6,
      left: triggerRect.left - (originRect?.left ?? 0),
      width: triggerRect.width,
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Fecha o dropdown se a página/modal rolar enquanto ele
   * está aberto — necessário porque `position: fixed` não acompanha o
   * scroll como o antigo `position: absolute` acompanhava, e a posição
   * calculada em `updateDropdownPosition` ficaria obsoleta (dropdown
   * "flutuando" longe do botão). Escuta na fase de captura
   * (`document`, `capture: true`) porque o scroll do `.p-dialog-content`
   * não borbulha até `window` — só a fase de captura alcança um
   * container com scroll aninhado.
   */
  private readonly _onScrollClose = (): void => {
    this.open.set(false);
    this._unbindScrollClose();
    this.onTouched();
  };

  private _bindScrollClose(): void {
    document.addEventListener('scroll', this._onScrollClose, { capture: true, passive: true });
  }

  private _unbindScrollClose(): void {
    document.removeEventListener('scroll', this._onScrollClose, { capture: true });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Escolhe um método da lista e propaga pro FormControl —
   * também desliga o listener de scroll (`_unbindScrollClose`), já que
   * o dropdown está fechando.
   */
  select(method: (typeof PAYMENT_METHODS)[number]): void {
    this.valueSignal.set(method.value);
    this.onChange(method.value);
    this.open.set(false);
    this._unbindScrollClose();
    this.onTouched();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Fecha o dropdown ao clicar fora dele — também desliga o
   * listener de scroll (`_unbindScrollClose`), já que o dropdown está
   * fechando.
   */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.open() && !this.elementRef.nativeElement.contains(event.target as Node)) {
      this.open.set(false);
      this._unbindScrollClose();
      this.onTouched();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Garante que o listener de scroll não vaze se o
   * componente for destruído com o dropdown ainda aberto — ex.: o
   * modal "Marcar como pago" é fechado (Cancelar/X/Esc) enquanto o
   * dropdown de forma de pagamento está aberto.
   */
  ngOnDestroy(): void {
    this._unbindScrollClose();
  }
}
