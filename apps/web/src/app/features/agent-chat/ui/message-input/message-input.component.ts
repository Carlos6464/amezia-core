import { Component, ElementRef, ViewChild, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslocoModule } from '@jsverse/transloco';

const MAX_HEIGHT_PX = 128;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-12
 * Descrição: Cápsula de input (textarea + botão de enviar dentro do
 * mesmo box arredondado) — layout replicado do projeto irmão. A
 * textarea cresce automaticamente até `MAX_HEIGHT_PX`, depois vira
 * scroll interno. Não sabe nada de HTTP/estado global, só emite o
 * texto digitado.
 */
@Component({
  selector: 'app-message-input',
  standalone: true,
  imports: [FormsModule, TranslocoModule],
  templateUrl: './message-input.component.html',
  styleUrl: './message-input.component.css',
})
export class MessageInputComponent {
  @ViewChild('inputRef') private readonly inputRef?: ElementRef<HTMLTextAreaElement>;

  readonly disabled = input(false);
  readonly send = output<string>();

  readonly text = signal('');

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Habilita o botão de enviar só com texto não-vazio (após
   * `trim()`) e enquanto o componente não estiver `disabled()` — evita
   * mensagem em branco e clique duplo durante `sending`/`waiting_response`.
   */
  readonly canSend = computed(() => this.text().trim().length > 0 && !this.disabled());

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Emite o conteúdo digitado (aparado), limpa o campo e
   * devolve a textarea à altura mínima — chamado pelo clique no botão
   * de enviar ou por Enter (sem Shift).
   */
  submit(): void {
    if (!this.canSend()) {
      return;
    }
    this.send.emit(this.text().trim());
    this.text.set('');
    this.resetHeight();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Enter envia; Shift+Enter quebra linha normalmente (a
   * textarea, diferente do `<input>` anterior, suporta múltiplas
   * linhas de verdade).
   */
  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.submit();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Ajusta a altura da textarea ao conteúdo digitado, até
   * `MAX_HEIGHT_PX` — depois disso o próprio campo rola internamente
   * (`overflow-y: auto` no CSS).
   */
  autoResize(): void {
    const element = this.inputRef?.nativeElement;
    if (!element) {
      return;
    }
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, MAX_HEIGHT_PX)}px`;
  }

  private resetHeight(): void {
    const element = this.inputRef?.nativeElement;
    if (element) {
      element.style.height = 'auto';
    }
  }
}
