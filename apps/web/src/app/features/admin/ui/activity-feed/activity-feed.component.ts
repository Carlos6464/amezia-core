import { DatePipe } from '@angular/common';
import { Component, input } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { AdminActivityEvent } from '@amezia/shared-types';

const ICON_BY_EVENT_TYPE: Record<string, string> = {
  user_registered: 'user-plus',
  user_upgraded: 'arrow-up',
  user_downgraded: 'arrow-down',
  user_canceled: 'x-circle',
};
const DEFAULT_ICON = 'activity';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-11
 * Descrição: Feed "burro" de atividade recente (build-context-11 §3.1,
 * T7) — reaproveitado pela Visão Geral do Admin. `message` já vem
 * pronto do backend (montado no momento da gravação), este componente
 * só formata a data e escolhe o ícone pelo `event_type`.
 */
@Component({
  selector: 'app-activity-feed',
  standalone: true,
  imports: [TranslocoModule, DatePipe],
  templateUrl: './activity-feed.component.html',
  styleUrl: './activity-feed.component.css',
})
export class ActivityFeedComponent {
  readonly items = input.required<AdminActivityEvent[]>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Resolve o ícone (nome usado no `[ngSwitch]` do
   * template) pelo `event_type` — cai num ícone genérico pra qualquer
   * tipo novo que o feed venha a ganhar no futuro (a lista de eventos
   * cresce sem migration, então o frontend precisa de um fallback).
   */
  protected iconFor(eventType: string): string {
    return ICON_BY_EVENT_TYPE[eventType] ?? DEFAULT_ICON;
  }
}
