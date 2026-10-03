import { Component, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { Category } from '@amezia/shared-types';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { CategoryIconComponent } from '../category-icon/category-icon.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-11
 * Descrição: Tabela desktop (>700px) de categorias — colunas Uso
 * (`transaction_count`) e Movimentado (`total_amount`) mostram o uso
 * real agregado pelo backend desde 2026-08-11 (antes disso ficavam com
 * placeholder "—", à espera de Transações existir — Observação 2 do
 * build-context-02). Categoria global mostra só o cadeado (RN-02);
 * privada mostra editar/excluir.
 */
@Component({
  selector: 'app-category-table',
  standalone: true,
  imports: [TranslocoModule, CategoryIconComponent, BrlAmountPipe],
  templateUrl: './category-table.component.html',
  styleUrl: './category-table.component.css',
})
export class CategoryTableComponent {
  categories = input.required<Category[]>();

  edit = output<Category>();
  remove = output<Category>();
}
