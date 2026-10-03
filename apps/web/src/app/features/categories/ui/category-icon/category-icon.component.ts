import { Component, computed, inject, input } from '@angular/core';
import { DomSanitizer, type SafeHtml } from '@angular/platform-browser';

import { CATEGORY_ICONS, DEFAULT_CATEGORY_ICON } from './category-icons';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Badge colorido com o ícone (Lucide) da categoria — antes
 * mostrava as duas primeiras letras do nome; passou a exigir um ícone de
 * verdade a pedido do usuário (categorias só com cor/iniciais ficavam
 * "rasas"). O ícone é fixo (SVG interno, sem chamada de rede em runtime)
 * e herda a cor da categoria via `currentColor`.
 */
@Component({
  selector: 'app-category-icon',
  standalone: true,
  templateUrl: './category-icon.component.html',
  styleUrl: './category-icon.component.css',
})
export class CategoryIconComponent {
  private readonly sanitizer = inject(DomSanitizer);

  color = input.required<string>();
  icon = input<string>(DEFAULT_CATEGORY_ICON);
  large = input(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Fundo do badge — a cor da categoria em baixa opacidade
   * (15%), recalculado sempre que `color()` mudar.
   */
  readonly background = computed(() => this._hexToRgba(this.color(), 0.15));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Markup interno do ícone (paths do Lucide) já sanitizado
   * para `[innerHTML]` — cai no ícone padrão (`tag`) se a chave recebida
   * não existir no registro (ex.: dado antigo/corrompido).
   */
  readonly iconMarkup = computed<SafeHtml>(() =>
    this.sanitizer.bypassSecurityTrustHtml(
      CATEGORY_ICONS[this.icon()] ?? CATEGORY_ICONS[DEFAULT_CATEGORY_ICON],
    ),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Converte uma cor hex (`#RRGGBB`) em `rgba(...)` com a
   * opacidade informada — usado para gerar o fundo suave do badge a
   * partir da cor sólida da categoria.
   */
  private _hexToRgba(hex: string, alpha: number): string {
    const match = /^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/.exec(hex);
    if (!match) {
      return hex;
    }
    const [r, g, b] = match.slice(1).map((part) => parseInt(part, 16));
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
}
