import { Component, computed, inject, model, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslocoModule } from '@jsverse/transloco';
import type { CategoryScope } from '@amezia/shared-types';

import { BreakpointService } from '../../../../core/viewport/breakpoint.service';
import {
  DropdownSelectComponent,
  type DropdownSelectOption,
} from '../../../../shared/ui/dropdown-select/dropdown-select.component';

export type ScopeFilter = CategoryScope | '';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Busca por nome + select de escopo — filtragem client-side
 * (dataset pequeno, sem paginação no backend, build-context-02 §3.3).
 * `searchTerm`/`scopeFilter` são two-way bound (model()) direto no
 * signal da página smart. Desde 2026-08-09 (mesmo ajuste já aplicado em
 * Transações), no mobile a barra inline vira um bottom sheet — o botão
 * que abre esse sheet fica no cabeçalho da página (fora deste
 * componente), então `openSheet()`/`activeFilterCount` são API pública.
 */
@Component({
  selector: 'app-category-filter-bar',
  standalone: true,
  imports: [FormsModule, TranslocoModule, DropdownSelectComponent],
  templateUrl: './category-filter-bar.component.html',
  styleUrl: './category-filter-bar.component.css',
})
export class CategoryFilterBarComponent {
  protected readonly breakpoint = inject(BreakpointService);

  searchTerm = model('');
  scopeFilter = model<ScopeFilter>('');

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Opções do dropdown de escopo — rótulos são chaves de
   * tradução, resolvidas pelo `DropdownSelectComponent`.
   */
  protected readonly scopeOptions: DropdownSelectOption[] = [
    { value: '', labelKey: 'categories.filterBar.allScopes' },
    { value: 'global', labelKey: 'categories.scope.global' },
    { value: 'private', labelKey: 'categories.scope.private' },
  ];

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Controla a visibilidade do bottom sheet mobile — pública
   * via `openSheet()`, chamada pelo botão de filtro no cabeçalho da
   * página (fora deste componente).
   */
  protected readonly sheetOpen = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Quantos filtros estão ativos — lido de fora pelo botão de
   * filtro no cabeçalho, pra mostrar um badge de contagem. `computed()`
   * porque `searchTerm`/`scopeFilter` já são Signals (mesmo padrão de
   * `TransactionFilterBarComponent.activeFilterCount`).
   */
  readonly activeFilterCount = computed(() => {
    let count = 0;
    if (this.searchTerm().trim() !== '') count++;
    if (this.scopeFilter() !== '') count++;
    return count;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Abre o bottom sheet — chamado de fora (botão de filtro no
   * cabeçalho da página, via `@ViewChild`).
   */
  openSheet(): void {
    this.sheetOpen.set(true);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Zera busca e escopo — usado pelo botão "Limpar" da barra
   * e também reaproveitado pelo estado "sem resultado" da página smart.
   */
  clear(): void {
    this.searchTerm.set('');
    this.scopeFilter.set('');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Fecha o bottom sheet mobile — os filtros já foram
   * aplicados ao vivo (client-side), então "aplicar" aqui só fecha o
   * sheet pro usuário ver o resultado por trás.
   */
  closeSheet(): void {
    this.sheetOpen.set(false);
  }
}
