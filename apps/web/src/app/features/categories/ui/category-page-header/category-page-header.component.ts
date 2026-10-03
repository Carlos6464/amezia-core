import { Component, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-09
 * Descrição: Cabeçalho da tela de Categorias — título + CTA "Nova
 * categoria" (sem limite de quantidade de categorias privadas desde
 * 2026-09-09).
 */
@Component({
  selector: 'app-category-page-header',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './category-page-header.component.html',
  styleUrl: './category-page-header.component.css',
})
export class CategoryPageHeaderComponent {
  create = output<void>();
}
