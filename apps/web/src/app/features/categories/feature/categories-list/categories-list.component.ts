import { Component, ViewChild, computed, inject, signal } from '@angular/core';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import type { Category, CategoryUpdateRequest } from '@amezia/shared-types';

import { BreakpointService } from '../../../../core/viewport/breakpoint.service';
import { OnboardingService } from '../../../../layout/onboarding/onboarding.service';
import { CategoriesService } from '../../data-access/categories.service';
import {
  CategoryFilterBarComponent,
  type ScopeFilter,
} from '../../ui/category-filter-bar/category-filter-bar.component';
import {
  CategoryFormDialogComponent,
  type CategoryFormValue,
} from '../../ui/category-form-dialog/category-form-dialog.component';
import { CategoryPageHeaderComponent } from '../../ui/category-page-header/category-page-header.component';
import { CategoryStatsStripComponent } from '../../ui/category-stats-strip/category-stats-strip.component';
import { CategoryTableComponent } from '../../ui/category-table/category-table.component';
import { CategoryCardListComponent } from '../../ui/category-card-list/category-card-list.component';

type ViewState = 'loading' | 'error' | 'empty-private' | 'no-results' | 'list';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Página smart de Categorias — orquestra CategoriesService,
 * filtros locais (busca/escopo) e os 5 estados de tela do build-context-02
 * §3.5 (normal, vazio de privadas, limite atingido, sem resultado de
 * busca, erro de carregamento).
 */
@Component({
  selector: 'app-categories-list',
  standalone: true,
  imports: [
    TranslocoModule,
    ConfirmDialogModule,
    CategoryPageHeaderComponent,
    CategoryFilterBarComponent,
    CategoryStatsStripComponent,
    CategoryTableComponent,
    CategoryCardListComponent,
    CategoryFormDialogComponent,
  ],
  templateUrl: './categories-list.component.html',
  styleUrl: './categories-list.component.css',
})
export class CategoriesListComponent {
  protected readonly categoriesService = inject(CategoriesService);
  protected readonly breakpoint = inject(BreakpointService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);
  private readonly onboarding = inject(OnboardingService);

  readonly searchTerm = signal('');
  readonly scopeFilter = signal<ScopeFilter>('');

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Referência ao componente de filtro — no mobile, o botão
   * que abre o bottom sheet fica no cabeçalho da página, não mais dentro
   * do próprio componente, então precisa de um jeito de acioná-lo de
   * fora (mesmo padrão de `TransactionListComponent`).
   */
  @ViewChild(CategoryFilterBarComponent) filterBar?: CategoryFilterBarComponent;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Abre o bottom sheet de filtro a partir do botão no
   * cabeçalho da página (mobile).
   */
  openFilterSheet(): void {
    this.filterBar?.openSheet();
  }

  readonly dialogVisible = signal(false);
  readonly dialogSaving = signal(false);
  readonly dialogError = signal<string | null>(null);
  readonly editingCategory = signal<Category | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Aplica busca por nome + filtro de escopo sobre a lista já
   * carregada — filtragem 100% client-side (build-context-02 §3.3),
   * dataset pequeno demais para justificar ida ao backend.
   */
  readonly filteredCategories = computed(() => {
    const term = this.searchTerm().trim().toLowerCase();
    const scope = this.scopeFilter();
    return this.categoriesService.categories().filter((category) => {
      if (scope && category.scope !== scope) {
        return false;
      }
      if (term && !category.name.toLowerCase().includes(term)) {
        return false;
      }
      return true;
    });
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Decide qual dos 5 estados da tela (Seção 3.5 do
   * build-context-02) renderizar — checa nessa ordem: carregando, erro,
   * "sem privadas" (filtro de escopo = Privada), "sem resultado de
   * busca", ou a lista normal.
   */
  readonly viewState = computed<ViewState>(() => {
    if (this.categoriesService.loading()) {
      return 'loading';
    }
    if (this.categoriesService.error()) {
      return 'error';
    }
    if (this.scopeFilter() === 'private' && this.categoriesService.privateCount() === 0) {
      return 'empty-private';
    }
    if (this.filteredCategories().length === 0) {
      return 'no-results';
    }
    return 'list';
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Dispara o carregamento inicial das categorias assim que a
   * página é montada — equivalente ao `ngOnInit()` da Seção 3.3.
   */
  constructor() {
    this.categoriesService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Recarrega a listagem — usado pelo botão "Tentar
   * novamente" do estado de erro.
   */
  retry(): void {
    this.categoriesService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Zera busca e escopo — usado pelo botão "Limpar filtros"
   * do estado "sem resultado de busca".
   */
  clearFilters(): void {
    this.searchTerm.set('');
    this.scopeFilter.set('');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-09
   * Descrição: Abre o modal em modo de criação (sem limite de quantidade
   * de categorias privadas desde 2026-09-09).
   */
  openCreateDialog(): void {
    this.editingCategory.set(null);
    this.dialogError.set(null);
    this.dialogVisible.set(true);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Abre o modal em modo de edição, pré-carregado com a
   * categoria clicada — só chamado para categorias privadas (a tabela
   * não emite `edit` para categorias globais).
   */
  openEditDialog(category: Category): void {
    this.editingCategory.set(category);
    this.dialogError.set(null);
    this.dialogVisible.set(true);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Fecha o modal e limpa qualquer erro pendente — chamado
   * tanto pelo cancelamento explícito quanto após um save bem-sucedido.
   */
  closeDialog(): void {
    this.dialogVisible.set(false);
    this.dialogError.set(null);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Recebe o payload do form-dialog e decide se cria ou
   * atualiza (com base em `editingCategory`) — em sucesso fecha o modal,
   * em erro 422 (limite/nome duplicado) mostra mensagem específica sem
   * fechar, para o usuário poder corrigir e tentar de novo. Criar (não
   * editar) uma categoria marca o item "category" do checklist de
   * onboarding. Toast de sucesso (build-context-13) varia a chave
   * conforme criação/edição — erro já tinha mensagem inline
   * (`dialogError`), sucesso ficava mudo (só o modal fechando).
   */
  onSave(value: CategoryFormValue): void {
    this.dialogSaving.set(true);
    this.dialogError.set(null);

    const editing = this.editingCategory();
    const request$ = editing
      ? this.categoriesService.update(editing.public_id, value as CategoryUpdateRequest)
      : this.categoriesService.create(value);

    request$.subscribe({
      next: () => {
        this.dialogSaving.set(false);
        this.closeDialog();
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('toasts.successTitle'),
          detail: this.transloco.translate(editing ? 'toasts.category.updated' : 'toasts.category.created'),
        });
        if (!editing) {
          this.onboarding.markDone('category');
        }
      },
      error: (err: { status?: number }) => {
        this.dialogSaving.set(false);
        this.dialogError.set(
          err.status === 422
            ? 'categories.form.errors.duplicateOrLimit'
            : 'categories.form.errors.generic',
        );
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Abre o `ConfirmDialog` do PrimeNG antes de excluir uma
   * categoria privada — a exclusão de verdade só acontece se o usuário
   * confirmar (`accept`); cancelar não tem efeito colateral nenhum.
   * Toast de sucesso/erro (build-context-13) — antes a exclusão ficava
   * muda, o usuário só percebia pela categoria sumir da tabela.
   */
  confirmDelete(category: Category): void {
    this.confirmationService.confirm({
      header: this.transloco.translate('categories.confirmDelete.header'),
      message: this.transloco.translate('categories.confirmDelete.message', {
        name: category.name,
      }),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: this.transloco.translate('categories.confirmDelete.accept'),
      rejectLabel: this.transloco.translate('categories.confirmDelete.reject'),
      // Severidade explícita — o default do tema deixava o botão de
      // excluir verde (lido como "success"), o que não faz sentido para
      // uma ação destrutiva. "danger" (vermelho) é o correto aqui.
      acceptButtonProps: { severity: 'danger' },
      rejectButtonProps: { severity: 'secondary', outlined: true },
      accept: () =>
        this.categoriesService.remove(category.public_id).subscribe({
          next: () => {
            this.messageService.add({
              severity: 'success',
              summary: this.transloco.translate('toasts.successTitle'),
              detail: this.transloco.translate('toasts.category.deleted'),
            });
          },
          error: () => {
            this.messageService.add({
              severity: 'error',
              summary: this.transloco.translate('toasts.errorTitle'),
              detail: this.transloco.translate('toasts.category.deleteError'),
            });
          },
        }),
    });
  }
}
