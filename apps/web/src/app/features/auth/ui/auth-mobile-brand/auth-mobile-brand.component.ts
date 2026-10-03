import { Component } from '@angular/core';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Logo + nome da Amezia exibidos só no mobile (≤900px), nas
 * 4 telas públicas de auth (login, registro, esqueci senha, redefinir
 * senha) — nessa largura o `.brand-col` inteiro (painel roxo com o
 * mesmo logo) some via `auth-split-page.css`, e sem substituto nenhuma
 * marca ficava visível na tela. Cores naturais do logo (sem o filtro
 * de inversão pra branco que o `AuthBrandPanelComponent` usa) porque
 * aqui o fundo é neutro (`var(--bg)`), não o painel roxo sólido.
 */
@Component({
  selector: 'app-auth-mobile-brand',
  standalone: true,
  templateUrl: './auth-mobile-brand.component.html',
  styleUrl: './auth-mobile-brand.component.css',
})
export class AuthMobileBrandComponent {}
