import { Component, ElementRef, HostListener, computed, forwardRef, inject, input, signal } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Uma opção do dropdown — `labelKey` é uma chave de tradução
 * (Transloco), não o texto já traduzido, pra não exigir que quem monta a
 * lista de opções injete `TranslocoService` só pra isso.
 */
export interface DropdownSelectOption {
  value: string;
  labelKey: string;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Combobox custom para listas curtas de opções fixas (tipo,
 * status, escopo — 2 a 4 itens), substituindo o `<select>` nativo cujo
 * estilo não acompanha o design system (pedido do usuário: "esse select
 * está horrível"). Mesmo padrão visual/de interação do
 * `CategorySelectComponent` (botão + painel via `ControlValueAccessor`),
 * mas sem campo de busca — não faz sentido buscar dentro de 2 ou 3
 * opções.
 */
@Component({
  selector: 'app-dropdown-select',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './dropdown-select.component.html',
  styleUrl: './dropdown-select.component.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DropdownSelectComponent),
      multi: true,
    },
  ],
})
export class DropdownSelectComponent implements ControlValueAccessor {
  private readonly elementRef = inject(ElementRef<HTMLElement>);

  options = input.required<DropdownSelectOption[]>();

  // Signal, não campo simples — computed() só reage a leituras de Signal
  // (mesmo bug já corrigido no CategorySelectComponent, ver DIARIO.md).
  private readonly valueSignal = signal('');
  disabled = false;

  readonly open = signal(false);

  // eslint-disable-next-line @typescript-eslint/no-empty-function
  private onChange: (value: string) => void = () => {};
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  onTouched: () => void = () => {};

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Opção atualmente selecionada — usada pro botão de
   * gatilho mostrar o rótulo certo.
   */
  readonly selectedOption = computed(() =>
    this.options().find((option) => option.value === this.valueSignal()),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Hook do ControlValueAccessor — escreve o valor vindo do
   * FormControl (ex.: `patchValue`).
   */
  writeValue(value: string): void {
    this.valueSignal.set(value ?? '');
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Abre/fecha o painel de opções.
   */
  toggle(): void {
    if (this.disabled) {
      return;
    }
    this.open.update((current) => !current);
    if (!this.open()) {
      this.onTouched();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Escolhe uma opção e propaga pro FormControl.
   */
  select(option: DropdownSelectOption): void {
    this.valueSignal.set(option.value);
    this.onChange(option.value);
    this.open.set(false);
    this.onTouched();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Fecha o painel ao clicar fora dele.
   */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.open() && !this.elementRef.nativeElement.contains(event.target as Node)) {
      this.open.set(false);
      this.onTouched();
    }
  }
}
