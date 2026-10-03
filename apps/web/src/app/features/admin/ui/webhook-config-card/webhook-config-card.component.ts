import { Component, input, signal } from '@angular/core';
import type { EvolutionInstance } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Card de configuração de webhook (build-context-06 §3.3) —
 * URL (com botão copiar), secret mascarado (só os últimos 4
 * caracteres, RN-05 — nunca chega inteiro no frontend, então não faz
 * sentido copiá-lo) e a lista fixa dos eventos que este módulo processa
 * (`webhook_events`, somente-leitura — não é campo configurável no
 * domínio, ver `EvolutionInstanceResponse.from_entity` no backend).
 */
@Component({
  selector: 'app-webhook-config-card',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './webhook-config-card.component.html',
  styleUrl: './webhook-config-card.component.css',
})
export class WebhookConfigCardComponent {
  readonly instance = input.required<EvolutionInstance>();

  protected readonly copied = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Copia a URL do webhook pra área de transferência —
   * mostra uma confirmação breve, some sozinha depois de 1.5s.
   */
  protected copyUrl(): void {
    navigator.clipboard.writeText(this.instance().webhook_url).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1500);
    });
  }
}
