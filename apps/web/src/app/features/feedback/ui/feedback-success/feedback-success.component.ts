import { Component, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Card de confirmação pós-envio (build-context-08 §3.1) —
 * sem redirecionamento, só um link para resetar o form in-place.
 */
@Component({
  selector: 'app-feedback-success',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './feedback-success.component.html',
  styleUrl: './feedback-success.component.css',
})
export class FeedbackSuccessComponent {
  readonly resetRequested = output<void>();
}
