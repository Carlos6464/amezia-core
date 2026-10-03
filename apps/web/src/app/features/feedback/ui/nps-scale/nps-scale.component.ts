import { Component, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Widget de NPS (build-context-08 §3.1/3.2) — escala de 11
 * botões (0–10), destaque visual por faixa (0–6 detrator, 7–8 neutro,
 * 9–10 promotor). Seleção opcional, no máximo uma nota marcada — dumb
 * component, só emite `npsChange` para o pai decidir o que fazer.
 */
@Component({
  selector: 'app-nps-scale',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './nps-scale.component.html',
  styleUrl: './nps-scale.component.css',
})
export class NpsScaleComponent {
  readonly value = input<number | null>(null);
  readonly npsChange = output<number>();

  protected readonly scores = Array.from({ length: 11 }, (_, index) => index);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Faixa visual de um score (RN de UI do protótipo) — usada
   * para a classe CSS de cada botão, independente de estar selecionado.
   */
  protected scoreClass(score: number): 'det' | 'neu' | 'pro' {
    if (score >= 9) return 'pro';
    if (score >= 7) return 'neu';
    return 'det';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Registra a nota escolhida e notifica o pai — sem opção de
   * desmarcar (mesmo comportamento do protótipo).
   */
  protected select(score: number): void {
    this.npsChange.emit(score);
  }
}
