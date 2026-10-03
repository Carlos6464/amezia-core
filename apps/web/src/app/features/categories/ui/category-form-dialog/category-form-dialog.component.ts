import { Component, effect, inject, input, output } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { TranslocoModule } from '@jsverse/transloco';
import type { Category } from '@amezia/shared-types';

import {
  CATEGORY_ICON_OPTIONS,
  DEFAULT_CATEGORY_ICON,
  type CategoryIconOption,
} from '../category-icon/category-icons';
import { CategoryIconComponent } from '../category-icon/category-icon.component';

// Paleta fechada — usuário escolhe uma cor pronta, nunca digita hex
// (feedback do usuário: hexadecimal não faz sentido para o usuário final).
const COLOR_PALETTE = [
  '#6366f1',
  '#818cf8',
  '#7c3aed',
  '#f43f5e',
  '#ef4444',
  '#ec4899',
  '#f59e0b',
  '#eab308',
  '#10b981',
  '#14b8a6',
  '#60a5fa',
  '#94a3b8',
];

export interface CategoryFormValue {
  name: string;
  color: string;
  icon: string;
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Modal de criar/editar categoria privada (PrimeNG Dialog) —
 * componente burro: só emite `save` com o payload, quem orquestra a
 * chamada ao CategoriesService é a página smart (feature/categories-list).
 * Desabilitado (nem abre) quando o limite de 3 privadas foi atingido em
 * modo de criação (Seção 3.5 do build-context-02). Cor e ícone são sempre
 * escolhidos de listas fechadas (paleta + ícones Lucide) — sem campo livre
 * de hexadecimal, que não faz sentido para o usuário final.
 */
@Component({
  selector: 'app-category-form-dialog',
  standalone: true,
  imports: [ReactiveFormsModule, DialogModule, TranslocoModule, CategoryIconComponent],
  templateUrl: './category-form-dialog.component.html',
  styleUrl: './category-form-dialog.component.css',
})
export class CategoryFormDialogComponent {
  private readonly fb = inject(FormBuilder);

  visible = input.required<boolean>();
  category = input<Category | null>(null);
  saving = input(false);
  errorKey = input<string | null>(null);

  dialogCancel = output<void>();
  save = output<CategoryFormValue>();

  readonly palette = COLOR_PALETTE;
  readonly iconOptions: CategoryIconOption[] = CATEGORY_ICON_OPTIONS;

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(50)]],
    color: [COLOR_PALETTE[0], Validators.required],
    icon: [DEFAULT_CATEGORY_ICON, Validators.required],
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Sempre que o modal abre, repopula o formulário a partir
   * da categoria em edição (ou dos defaults, em modo de criação) — sem
   * isso, reabrir o modal reaproveitaria os valores digitados da vez
   * anterior (bug real encontrado na validação em browser desta sessão).
   */
  private readonly _syncFormWithCategory = effect(() => {
    const current = this.category();
    if (this.visible()) {
      this.form.reset({
        name: current?.name ?? '',
        color: current?.color ?? COLOR_PALETTE[0],
        icon: current?.icon ?? DEFAULT_CATEGORY_ICON,
      });
    }
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: `true` quando o modal foi aberto para editar uma
   * categoria existente (`category()` preenchido); `false` em modo de
   * criação — decide título, texto do botão e reset do formulário.
   */
  get isEditMode(): boolean {
    return this.category() !== null;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Aplica a cor escolhida na paleta ao formulário — clique
   * num `.palette-dot`.
   */
  pickColor(color: string): void {
    this.form.controls.color.setValue(color);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Aplica o ícone escolhido no grid ao formulário — clique
   * num `.icon-option`.
   */
  pickIcon(icon: string): void {
    this.form.controls.icon.setValue(icon);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Valida o formulário e emite `save` com o payload — não
   * chama a API diretamente (componente burro), quem orquestra é a
   * página smart. Ignora submits duplicados enquanto `saving()` é true.
   */
  submit(): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }
    this.save.emit(this.form.getRawValue());
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Callback do `(visibleChange)` do PrimeNG Dialog — dispara
   * quando o usuário fecha o modal por fora (máscara, Esc, X), não só
   * pelo botão Cancelar; emite `dialogCancel` para a página smart
   * sincronizar seu próprio Signal de visibilidade.
   */
  onVisibleChange(visible: boolean): void {
    if (!visible) {
      this.dialogCancel.emit();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: `true` quando o campo tem erro E já foi tocado — controla
   * a borda vermelha e a mensagem inline do nome. `color`/`icon` não
   * passam por aqui: são escolhidos de listas fechadas (sempre têm um
   * valor via `pickColor`/`pickIcon`/reset), `Validators.required` neles
   * é defensivo, não alcançável pela UI. Bug real relatado pelo usuário:
   * `markAllAsTouched()` já rodava em `submit()`, mas nada no template
   * lia `invalid`/`touched` do campo `name`.
   */
  protected fieldInvalid(name: 'name'): boolean {
    const control = this.form.get(name);
    return !!control && control.invalid && control.touched;
  }
}
