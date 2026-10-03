import { Component, ElementRef, HostListener, computed, inject, model, signal } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

import { CategoriesService } from '../../../categories/data-access/categories.service';
import { CategoryIconComponent } from '../../../categories/ui/category-icon/category-icon.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Seletor de categoria da filter-bar de Reports — mesmo
 * padrão visual/de interação do `CategorySelectComponent` (build-context-03),
 * mas sem criação inline (é só filtro, não formulário) e com uma opção
 * "Todas as categorias" extra no topo, que `DropdownSelectComponent`
 * (opções estáticas traduzidas) e `CategorySelectComponent` (sempre
 * exige uma seleção) não cobrem sozinhos. `model()` two-way em vez de
 * `ControlValueAccessor`: a filter-bar de Reports não usa Reactive
 * Forms, mesmo padrão de `type`/`status` em `TransactionFilterBarComponent`.
 */
@Component({
  selector: 'app-report-category-select',
  standalone: true,
  imports: [TranslocoModule, CategoryIconComponent],
  templateUrl: './report-category-select.component.html',
  styleUrl: './report-category-select.component.css',
})
export class ReportCategorySelectComponent {
  protected readonly categoriesService = inject(CategoriesService);
  private readonly elementRef = inject(ElementRef<HTMLElement>);

  categoryId = model('');

  readonly open = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Carrega as categorias ao montar — autossuficiente, mesmo
   * padrão de `CategorySelectComponent`.
   */
  constructor() {
    this.categoriesService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Categoria selecionada (para o botão de gatilho) —
   * `undefined` quando `categoryId()` é `''` (opção "Todas").
   */
  readonly selectedCategory = computed(() =>
    this.categoriesService.categories().find((category) => category.public_id === this.categoryId()),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Abre/fecha o painel de opções.
   */
  toggle(): void {
    this.open.update((current) => !current);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Escolhe uma categoria (ou `''` para "Todas") e propaga
   * via `categoryId` (two-way `model()`).
   */
  select(categoryId: string): void {
    this.categoryId.set(categoryId);
    this.open.set(false);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Fecha o painel ao clicar fora dele.
   */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.open() && !this.elementRef.nativeElement.contains(event.target as Node)) {
      this.open.set(false);
    }
  }
}
