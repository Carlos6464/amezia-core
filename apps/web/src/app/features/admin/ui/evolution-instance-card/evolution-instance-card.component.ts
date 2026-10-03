import { DatePipe } from '@angular/common';
import { Component, computed, input, output } from '@angular/core';
import type { EvolutionInstance } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Card de status da instância Evolution (build-context-06
 * §3.3) — status/número/instância/conectado desde/última mensagem, QR
 * code enquanto `status=connecting` (o polling que atualiza `instance()`
 * a cada tick mora na página, não aqui), ações Conectar/Sincronizar/
 * Desconectar.
 */
@Component({
  selector: 'app-evolution-instance-card',
  standalone: true,
  imports: [TranslocoModule, DatePipe],
  templateUrl: './evolution-instance-card.component.html',
  styleUrl: './evolution-instance-card.component.css',
})
export class EvolutionInstanceCardComponent {
  readonly instance = input.required<EvolutionInstance>();
  readonly pending = input(false);
  readonly connectClick = output<void>();
  readonly syncClick = output<void>();
  readonly disconnectClick = output<void>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Monta a data URI do QR code — a Evolution API pode
   * devolver o base64 já prefixado (`data:image/...`) ou cru, então
   * normaliza os dois formatos aqui em vez de assumir um só.
   */
  protected readonly qrCodeSrc = computed(() => {
    const qrCode = this.instance().qr_code;
    if (!qrCode) {
      return null;
    }
    return qrCode.startsWith('data:') ? qrCode : `data:image/png;base64,${qrCode}`;
  });
}
