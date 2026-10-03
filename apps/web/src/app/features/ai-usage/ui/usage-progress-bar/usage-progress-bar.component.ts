import { Component, computed, input } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Uma barra de uso "burra" (build-context-10 §3.2, T11) —
 * rótulo, valor/limite e percentual, reaproveitada pelas 4 métricas de
 * `settings-usage-page` (conversas de IA, relatórios, Bot WhatsApp,
 * exportações CSV). `limit() === null` é ilimitado — não desenha barra
 * nenhuma, só o rótulo "Ilimitado".
 */
@Component({
  selector: 'app-usage-progress-bar',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './usage-progress-bar.component.html',
  styleUrl: './usage-progress-bar.component.css',
})
export class UsageProgressBarComponent {
  readonly labelKey = input.required<string>();
  readonly used = input.required<number>();
  readonly limit = input<number | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Percentual consumido (0–100), nunca ultrapassa 100%
   * visualmente mesmo com o limite estourado — `0` quando ilimitado
   * (a barra some do template nesse caso, então o valor não é lido).
   */
  protected readonly percent = computed(() => {
    const limit = this.limit();
    if (limit === null || limit <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((this.used() / limit) * 100));
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: `true` a partir de 80% do limite — controla a cor âmbar
   * da barra e do texto, mesmo padrão visual de alerta já usado no
   * produto (build-context-10 §3.2).
   */
  protected readonly isNearLimit = computed(() => {
    const limit = this.limit();
    return limit !== null && limit > 0 && this.used() / limit >= 0.8;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: `true` quando o uso já atingiu ou passou do limite —
   * controla a cor vermelha (mais forte que o âmbar de `isNearLimit`).
   */
  protected readonly isOverLimit = computed(() => {
    const limit = this.limit();
    return limit !== null && this.used() >= limit;
  });
}
