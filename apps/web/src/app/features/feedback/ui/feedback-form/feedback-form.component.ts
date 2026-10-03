import { Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { FeedbackType } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

const MAX_SUBJECT_LENGTH = 150;
const MAX_MESSAGE_LENGTH = 1000;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Campos "Assunto"/"Mensagem" + botão de envio
 * (build-context-08 §3.1/3.2) — dumb component, só emite
 * `submitRequested` com os valores digitados; hint/placeholder do
 * assunto trocam conforme o `type` selecionado no chip do pai.
 */
@Component({
  selector: 'app-feedback-form',
  standalone: true,
  imports: [FormsModule, TranslocoModule],
  templateUrl: './feedback-form.component.html',
  styleUrl: './feedback-form.component.css',
})
export class FeedbackFormComponent {
  readonly type = input.required<FeedbackType>();
  readonly userName = input<string | null>(null);
  readonly submitting = input(false);
  readonly submitRequested = output<{ subject: string; message: string }>();

  protected readonly maxSubjectLength = MAX_SUBJECT_LENGTH;
  protected readonly maxMessageLength = MAX_MESSAGE_LENGTH;

  protected readonly subject = signal('');
  protected readonly message = signal('');

  protected readonly messageLength = computed(() => this.message().length);
  protected readonly canSubmit = computed(
    () => this.message().trim().length > 0 && !this.submitting(),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Dispara o envio com os valores atuais — botão já fica
   * desabilitado quando `canSubmit()` é falso, então esta guarda é só
   * defensiva (ex.: submit via Enter no campo assunto).
   */
  protected onSubmit(): void {
    if (!this.canSubmit()) return;
    this.submitRequested.emit({ subject: this.subject().trim(), message: this.message() });
  }
}
