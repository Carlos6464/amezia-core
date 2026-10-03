import { Component, forwardRef, input } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

let nextId = 0;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Input de senha com botão de mostrar/ocultar (padrão
 * .pw-wrap/.pw-eye do protótipo register-form), integrado a Reactive
 * Forms via ControlValueAccessor. Reaproveitado em login, registro e
 * redefinição de senha.
 */
@Component({
  selector: 'app-password-field',
  standalone: true,
  templateUrl: './password-field.component.html',
  styleUrl: './password-field.component.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PasswordFieldComponent),
      multi: true,
    },
  ],
})
export class PasswordFieldComponent implements ControlValueAccessor {
  label = input('');
  placeholder = input('');
  autocomplete = input<'new-password' | 'current-password'>('current-password');

  readonly inputId = `pw-field-${nextId++}`;

  value = '';
  visible = false;
  disabled = false;

  // eslint-disable-next-line @typescript-eslint/no-empty-function
  private onChange: (value: string) => void = () => {};
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  onTouched: () => void = () => {};

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Hook do ControlValueAccessor — Angular chama isso para
   * escrever um valor no componente programaticamente (ex.: `form.reset()`).
   */
  writeValue(value: string): void {
    this.value = value ?? '';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Hook do ControlValueAccessor — registra o callback que o
   * Angular usa para saber quando o valor mudou (chamado em `onInput`).
   */
  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Hook do ControlValueAccessor — registra o callback de
   * "blur" que marca o FormControl como touched.
   */
  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Hook do ControlValueAccessor — reflete `[disabled]` do
   * FormControl no input real.
   */
  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Alterna entre mostrar a senha em texto puro ou mascarada.
   */
  toggle(): void {
    this.visible = !this.visible;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Lê o valor digitado e propaga pro FormControl via o
   * callback registrado em `registerOnChange`.
   */
  onInput(event: Event): void {
    this.value = (event.target as HTMLInputElement).value;
    this.onChange(this.value);
  }
}
