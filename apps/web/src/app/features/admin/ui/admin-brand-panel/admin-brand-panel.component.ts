import { Component } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Painel de marca do lado esquerdo de `/admin/login` — mesmo
 * layout de `AuthBrandPanelComponent` (logo + headline + destaques),
 * cópia própria da feature Admin (não importa o componente do cliente,
 * painéis isolados) com conteúdo específico do painel operador.
 */
@Component({
  selector: 'app-admin-brand-panel',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './admin-brand-panel.component.html',
  styleUrl: './admin-brand-panel.component.css',
})
export class AdminBrandPanelComponent {}
