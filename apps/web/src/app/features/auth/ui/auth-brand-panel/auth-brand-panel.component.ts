import { Component } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Painel de marca (logo + headline + 3 destaques) do lado
 * esquerdo das telas públicas de auth — reaproveitado por login, registro,
 * esqueci-senha e redefinir-senha para manter o layout consistente entre
 * as 4 telas. Colapsado em telas estreitas via `.brand-col` (o wrapper no
 * template de cada página), não aqui — ver `auth-split-page.css`.
 */
@Component({
  selector: 'app-auth-brand-panel',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './auth-brand-panel.component.html',
  styleUrl: './auth-brand-panel.component.css',
})
export class AuthBrandPanelComponent {}
