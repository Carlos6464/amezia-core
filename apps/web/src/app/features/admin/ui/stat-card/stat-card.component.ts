import { Component, input } from '@angular/core';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: KPI card reutilizado pelas 4 telas do Admin (build-context-06
 * §3.1) — ícone via content projection (`[icon]`), texto já resolvido
 * pelo componente pai (o próprio `| transloco` acontece lá).
 */
@Component({
  selector: 'app-stat-card',
  standalone: true,
  templateUrl: './stat-card.component.html',
  styleUrl: './stat-card.component.css',
})
export class StatCardComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string>();
  readonly sub = input<string | null>(null);
}
