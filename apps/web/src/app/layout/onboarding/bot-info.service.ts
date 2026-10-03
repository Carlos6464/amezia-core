import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { BotInfo } from '@amezia/shared-types';

const BASE_URL = '/api/v1/bot';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Número do bot WhatsApp + disponibilidade (`GET /bot/info`)
 * — usado pelo passo "salvar número do bot" do onboarding, exibido em
 * `/settings/profile`. Serviço próprio (não dentro de `OnboardingService`)
 * porque a informação em si não é estado de onboarding, só é consumida
 * por ele.
 */
@Injectable({ providedIn: 'root' })
export class BotInfoService {
  private readonly http = inject(HttpClient);

  readonly botInfo = signal<BotInfo | null>(null);
  readonly loading = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Busca o número do bot — silenciosamente ignora erro (a
   * tela de perfil não deve travar por causa de um card secundário).
   */
  load(): void {
    this.loading.set(true);
    this.http.get<BotInfo>(`${BASE_URL}/info`).subscribe({
      next: (info) => {
        this.botInfo.set(info);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
