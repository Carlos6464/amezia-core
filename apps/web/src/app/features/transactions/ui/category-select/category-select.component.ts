import { Component, ElementRef, HostListener, computed, forwardRef, inject, input, signal } from '@angular/core';
import { ControlValueAccessor, FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { MessageService } from 'primeng/api';
import type { Category } from '@amezia/shared-types';

import { CategoriesService } from '../../../categories/data-access/categories.service';
import {
  CategoryFormDialogComponent,
  type CategoryFormValue,
} from '../../../categories/ui/category-form-dialog/category-form-dialog.component';
import { CategoryIconComponent } from '../../../categories/ui/category-icon/category-icon.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Seletor de categoria pesquisável (combobox), integrado a
 * Reactive Forms via ControlValueAccessor — substitui o `<select>` plano
 * original a pedido do usuário. Mostra categorias globais e privadas
 * separadas, com busca por nome, e permite criar uma categoria privada
 * nova sem sair do formulário de transação (reaproveita
 * `CategoryFormDialogComponent` do build-context-02).
 */
@Component({
  selector: 'app-category-select',
  standalone: true,
  imports: [FormsModule, TranslocoModule, CategoryIconComponent, CategoryFormDialogComponent],
  templateUrl: './category-select.component.html',
  styleUrl: './category-select.component.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CategorySelectComponent),
      multi: true,
    },
  ],
})
export class CategorySelectComponent implements ControlValueAccessor {
  protected readonly categoriesService = inject(CategoriesService);
  private readonly elementRef = inject(ElementRef<HTMLElement>);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);

  // Signal, não campo simples — um `computed()` só reage a leituras de
  // Signal; escrever `this.value = x` direto nunca dispararia
  // `selectedCategory` de novo (bug real encontrado na validação em
  // browser desta sessão: o botão continuava mostrando o placeholder
  // mesmo depois de escolher uma categoria).
  private readonly valueSignal = signal('');
  disabled = false;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Estilo de erro do botão de gatilho — não vem do
   * `ControlValueAccessor` (Angular não propaga `invalid`/`touched` do
   * `FormControl` pro componente sozinho); quem usa o combobox precisa
   * passar explicitamente, ex. `[invalid]="fieldInvalid('categoryId')"`.
   */
  invalid = input(false);

  readonly open = signal(false);
  readonly searchTerm = signal('');
  readonly createDialogVisible = signal(false);
  readonly creating = signal(false);
  readonly createError = signal<string | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-empty-function
  private onChange: (value: string) => void = () => {};
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  onTouched: () => void = () => {};

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Carrega as categorias ao montar — o componente é
   * autossuficiente, não depende de quem o usa lembrar de chamar
   * `CategoriesService.load()` antes.
   */
  constructor() {
    this.categoriesService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Categoria atualmente selecionada (para o botão de
   * gatilho) — `undefined` enquanto as categorias ainda não carregaram
   * ou nenhuma foi escolhida.
   */
  readonly selectedCategory = computed(() =>
    this.categoriesService.categories().find((category) => category.public_id === this.valueSignal()),
  );

  readonly filteredGlobal = computed(() => this.filterByTerm(this.categoriesService.globalCategories()));
  readonly filteredPrivate = computed(() => this.filterByTerm(this.categoriesService.privateCategories()));

  private filterByTerm(list: Category[]): Category[] {
    const term = this.searchTerm().trim().toLowerCase();
    if (!term) {
      return list;
    }
    return list.filter((category) => category.name.toLowerCase().includes(term));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Hook do ControlValueAccessor — Angular chama isso para
   * escrever um valor no componente programaticamente (ex.: `form.reset()`
   * ou `patchValue()` ao pré-preencher a edição).
   */
  writeValue(value: string): void {
    this.valueSignal.set(value ?? '');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Hook do ControlValueAccessor — registra o callback que o
   * Angular usa para saber quando o valor mudou.
   */
  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Hook do ControlValueAccessor — registra o callback de
   * "touched", disparado quando o dropdown fecha.
   */
  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Hook do ControlValueAccessor — reflete `[disabled]` do
   * FormControl no botão de gatilho.
   */
  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Abre/fecha o dropdown — zera a busca a cada abertura.
   */
  toggle(): void {
    if (this.disabled) {
      return;
    }
    this.open.update((current) => !current);
    if (this.open()) {
      this.searchTerm.set('');
    } else {
      this.onTouched();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Escolhe uma categoria da lista e propaga pro FormControl.
   */
  select(category: Category): void {
    this.valueSignal.set(category.public_id);
    this.onChange(category.public_id);
    this.open.set(false);
    this.onTouched();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-09
   * Descrição: Abre o modal de criar categoria (sem limite de quantidade
   * de categorias privadas desde 2026-09-09).
   */
  openCreateDialog(): void {
    this.createError.set(null);
    this.createDialogVisible.set(true);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Cria a categoria a partir do payload do modal e já a
   * seleciona no combobox — o usuário nunca precisa sair do formulário
   * de transação pra usar uma categoria que ainda não existia. Toast de
   * sucesso (build-context-13) — erro já tinha mensagem inline no
   * próprio modal (`createError`), sucesso ficava mudo.
   */
  onCreateSave(formValue: CategoryFormValue): void {
    this.creating.set(true);
    this.createError.set(null);
    this.categoriesService.create(formValue).subscribe({
      next: (category) => {
        this.creating.set(false);
        this.createDialogVisible.set(false);
        this.valueSignal.set(category.public_id);
        this.onChange(category.public_id);
        this.open.set(false);
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('toasts.successTitle'),
          detail: this.transloco.translate('toasts.category.created'),
        });
      },
      error: (err: { status?: number }) => {
        this.creating.set(false);
        this.createError.set(
          err.status === 422 ? 'categories.form.errors.duplicateOrLimit' : 'categories.form.errors.generic',
        );
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Fecha o dropdown ao clicar fora dele — o `elementRef`
   * cobre o botão de gatilho e o painel, então qualquer clique de fora
   * dos dois fecha.
   */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.open() && !this.elementRef.nativeElement.contains(event.target as Node)) {
      this.open.set(false);
      this.onTouched();
    }
  }
}
