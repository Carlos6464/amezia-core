import { Component, input } from '@angular/core';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Botão "Continuar com Google" — um link puro para
 * `GET /api/v1/auth/google`, que dispara um redirect de página inteira
 * pro consentimento real do Google (fluxo OAuth2 authorization code,
 * `apps/api/src/presentation/api/v1/auth/router.py`). Substitui a versão
 * anterior baseada em Google Identity Services (`renderButton()`): não há
 * mais nenhum widget/iframe do Google embutido nesta página, então o
 * visual do botão é 100% controlado pelo CSS deste componente — sem as
 * restrições de branding, tamanho fixo ou bugs de renderização (iframe
 * 0x0, botão branco fixo no dark mode) que o widget embutido impunha.
 */
@Component({
  selector: 'app-google-auth-button',
  standalone: true,
  templateUrl: './google-auth-button.component.html',
  styleUrl: './google-auth-button.component.css',
})
export class GoogleAuthButtonComponent {
  label = input('Continuar com Google');
}
