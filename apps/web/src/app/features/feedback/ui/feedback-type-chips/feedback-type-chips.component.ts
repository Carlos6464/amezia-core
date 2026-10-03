import { Component, input, output } from '@angular/core';
import type { FeedbackType } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

const TYPES: FeedbackType[] = ['praise', 'suggestion', 'bug', 'other'];

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Chips de tipo de feedback (build-context-08 §3.1/3.2) —
 * "Elogio/Sugestão/Bug-Problema/Outro", seleção única. Dumb component,
 * só emite `typeChange` para o pai decidir o que fazer.
 */
@Component({
  selector: 'app-feedback-type-chips',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './feedback-type-chips.component.html',
  styleUrl: './feedback-type-chips.component.css',
})
export class FeedbackTypeChipsComponent {
  readonly selected = input<FeedbackType>('praise');
  readonly typeChange = output<FeedbackType>();

  protected readonly types = TYPES;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Registra o tipo escolhido e notifica o pai.
   */
  protected select(type: FeedbackType): void {
    this.typeChange.emit(type);
  }
}
