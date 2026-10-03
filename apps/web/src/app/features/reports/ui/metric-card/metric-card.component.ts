import { Component, input } from '@angular/core';

export type MetricCardTone = 'neutral' | 'red' | 'green';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Cartão de métrica genérico — reutilizado pela grade de 4
 * métricas do Dashboard e pela stats-strip do Reports (build-context-05
 * §1.2, "os dois consomem os mesmos endpoints de agregação"). Ícone via
 * `<ng-content select="[icon]" />` para cada tela escolher o SVG/cor
 * certos sem o componente precisar de um catálogo de ícones próprio.
 */
@Component({
  selector: 'app-metric-card',
  standalone: true,
  templateUrl: './metric-card.component.html',
  styleUrl: './metric-card.component.css',
})
export class MetricCardComponent {
  label = input.required<string>();
  value = input.required<string>();
  subtitle = input<string | null>(null);
  tone = input<MetricCardTone>('neutral');
  iconColor = input('var(--accent)');
  iconBackground = input('var(--acc-s)');
  iconBorderColor = input('rgba(99, 102, 241, 0.2)');
}
