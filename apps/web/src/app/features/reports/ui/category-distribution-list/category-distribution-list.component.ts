import { Component, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { CategoryDistributionItem } from '@amezia/shared-types';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Lista de distribuição por categoria — usada em dois modos
 * (build-context-05 §1.2): "top 3" do Dashboard (chamador já passa a
 * lista fatiada em `items()`) e ranking completo do Reports (todas as
 * categorias). O componente em si não sabe qual modo é: só renderiza o
 * que recebe, ordenado como veio do backend (`total` desc).
 * `clickable` (2026-08-18, default `false`) liga a interação de clique
 * — só o Dashboard usa, pra abrir o modal de transações da categoria;
 * Reports continua só informativo, sem mudar nada lá.
 */
@Component({
  selector: 'app-category-distribution-list',
  standalone: true,
  imports: [TranslocoModule, BrlAmountPipe],
  templateUrl: './category-distribution-list.component.html',
  styleUrl: './category-distribution-list.component.css',
})
export class CategoryDistributionListComponent {
  items = input.required<CategoryDistributionItem[]>();
  clickable = input(false);
  itemClick = output<CategoryDistributionItem>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Clique numa linha da lista — só emite quando
   * `clickable()` está ligado (Dashboard); em Reports o `role="button"`
   * do template nem existe, então isso nunca dispara lá.
   */
  protected onItemClick(item: CategoryDistributionItem): void {
    if (this.clickable()) {
      this.itemClick.emit(item);
    }
  }
}
