import { Component, input } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { Category } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-11
 * Descrição: Faixa de estatísticas (Visíveis / Globais / Privadas / Mais
 * usada). "Mais usada" mostra a categoria real com mais transações
 * desde 2026-08-11 (`CategoriesService.mostUsedCategory`) — antes disso
 * ficava como placeholder "—", à espera de Transações existir pra
 * agregar uso real (Observação 2 do build-context-02).
 */
@Component({
  selector: 'app-category-stats-strip',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './category-stats-strip.component.html',
  styleUrl: './category-stats-strip.component.css',
})
export class CategoryStatsStripComponent {
  visibleCount = input(0);
  globalCount = input(0);
  privateCount = input(0);
  mostUsedCategory = input<Category | null>(null);
}
