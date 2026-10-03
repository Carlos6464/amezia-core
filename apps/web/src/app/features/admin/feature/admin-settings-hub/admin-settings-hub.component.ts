import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { AuthService } from '../../../../core/auth/auth.service';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Gera as iniciais do avatar — mesma lógica de
 * `SettingsHubComponent` (painel cliente), duplicada aqui (painéis
 * isolados, sem import cruzado).
 */
function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Hub de Configurações do Admin (`/admin/settings`) — mesmo
 * papel do `SettingsHubComponent` do painel cliente: 5ª aba da barra
 * inferior mobile, reúne o que não cabe nas 4 abas principais (aqui só
 * Perfil + Sair, o Admin não tem um equivalente de "Categorias"). No
 * desktop o mesmo destino (Perfil) já está direto no dropdown do
 * avatar — esta tela existe pra dar ao mobile o mesmo padrão de
 * navegação do painel cliente, pedido explícito do usuário em
 * 2026-08-15.
 */
@Component({
  selector: 'app-admin-settings-hub',
  standalone: true,
  imports: [RouterLink, TranslocoModule],
  templateUrl: './admin-settings-hub.component.html',
  styleUrl: './admin-settings-hub.component.css',
})
export class AdminSettingsHubComponent {
  protected readonly authService = inject(AuthService);

  protected readonly initials = computed(() => initialsOf(this.authService.currentUser()?.name ?? ''));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Aciona o logout a partir do item "Sair" do hub — volta
   * pra `/admin/login`, nunca `/login` (painéis isolados).
   */
  logout(): void {
    this.authService.logout('/admin/login');
  }
}
