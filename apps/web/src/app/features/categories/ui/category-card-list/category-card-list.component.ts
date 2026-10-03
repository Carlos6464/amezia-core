import { Component, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { Category } from '@amezia/shared-types';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { CategoryIconComponent } from '../category-icon/category-icon.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Lista em cards para mobile (≤700px) — mesma informação da
 * tabela desktop, layout do protótipo (dt-card-list).
 */
@Component({
  selector: 'app-category-card-list',
  standalone: true,
  imports: [TranslocoModule, CategoryIconComponent, BrlAmountPipe],
  templateUrl: './category-card-list.component.html',
  styleUrl: './category-card-list.component.css',
})
export class CategoryCardListComponent {
  categories = input.required<Category[]>();

  edit = output<Category>();
  remove = output<Category>();
}
