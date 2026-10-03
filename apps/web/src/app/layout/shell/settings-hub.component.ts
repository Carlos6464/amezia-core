import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { AuthService } from '../../core/auth/auth.service';
import { SubscriptionService } from '../../features/subscription/data-access/subscription.service';
import { OnboardingService } from '../onboarding/onboarding.service';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Gera as iniciais do avatar (primeiro + último nome) a
 * partir do nome completo — mesma lógica de `AppShellComponent`, mas o
 * hub de Configurações não injeta o shell, então duplica a função em vez
 * de acoplar os dois componentes por um detalhe de apresentação.
 */
function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Hub de Configurações — aba "Configurações" da barra inferior
 * mobile (ajuste de navegação de 2026-08-09). Reúne as funções que não
 * cabem nas 4 abas principais (Perfil, Categorias, Sair), no lugar de uma
 * sidebar sempre visível como o desktop tem. No desktop essa página
 * também é acessível (ex.: digitando a URL), mas não é o caminho
 * primário — lá Perfil e Categorias continuam como itens diretos da
 * sidebar.
 */
@Component({
  selector: 'app-settings-hub',
  standalone: true,
  imports: [RouterLink, TranslocoModule],
  templateUrl: './settings-hub.component.html',
  styleUrl: './settings-hub.component.css',
})
export class SettingsHubComponent {
  protected readonly authService = inject(AuthService);
  private readonly subscriptionService = inject(SubscriptionService);
  private readonly onboarding = inject(OnboardingService);

  protected readonly initials = computed(() => initialsOf(this.authService.currentUser()?.name ?? ''));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: `true` em acesso de teste Premium vitalício concedido
   * pelo admin — esconde o item "Planos" do hub, mesmo motivo de
   * `AppShellComponent.isAdminTestAccess`. `AppShellComponent` já
   * carrega `mySubscription()` no `ngOnInit` do shell pai, este
   * componente só lê o Signal já populado (mesmo singleton
   * `providedIn: 'root'`), sem recarregar.
   */
  protected readonly isAdminTestAccess = computed(
    () => this.subscriptionService.mySubscription()?.is_admin_test_access ?? false,
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: `true` também pra papel `admin` — mesmo motivo de
   * `AppShellComponent.hidePlanArea` (pedido do usuário: um admin
   * navegando no app do cliente comum não pode ver a área de plano).
   */
  protected readonly hidePlanArea = computed(
    () => this.isAdminTestAccess() || this.authService.currentUser()?.role === 'admin',
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Aciona o logout (limpa sessão + navega para /login) a
   * partir do item "Sair" do hub.
   */
  logout(): void {
    this.authService.logout();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: "Reiniciar tour" — zera o progresso do onboarding
   * (local + backend) e reexibe o checklist/FAB, mesmo se o usuário já
   * tinha concluído ou dispensado antes.
   */
  restartOnboarding(): void {
    this.onboarding.resetOnboarding();
  }
}
