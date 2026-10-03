import { Component, OnInit, input, output, signal } from '@angular/core';
import type { AdminUser, UserRole } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

import { RoleBadgeComponent } from '../role-badge/role-badge.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Modal de troca de papel (build-context-06 §3.3) — aberto
 * ao clicar numa linha da tabela de usuários. `saving()` desabilita o
 * botão de confirmar durante a chamada, evitando duplo clique. Desde
 * 2026-09-15, ganhou uma 2ª seção independente — o toggle de acesso de
 * teste Premium vitalício (pedido direto do usuário, fora de qualquer
 * build-context) — que salva na hora ao ser clicado, sem depender do
 * botão "Salvar" do papel (as duas ações não têm relação nenhuma entre
 * si, então não faz sentido travar uma esperando a outra).
 */
@Component({
  selector: 'app-change-role-modal',
  standalone: true,
  imports: [TranslocoModule, RoleBadgeComponent],
  templateUrl: './change-role-modal.component.html',
  styleUrl: './change-role-modal.component.css',
})
export class ChangeRoleModalComponent implements OnInit {
  readonly user = input.required<AdminUser>();
  readonly saving = input(false);
  readonly savingTestAccess = input(false);
  readonly closeModal = output<void>();
  readonly confirmRole = output<UserRole>();
  readonly toggleTestAccess = output<boolean>();

  protected readonly selectedRole = signal<UserRole>('user');

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Inicializa a seleção com o papel atual do usuário — só
   * roda uma vez, quando o modal é criado (o pai monta uma instância
   * nova a cada abertura via `@if`).
   */
  ngOnInit(): void {
    this.selectedRole.set(this.user().role);
  }

  protected selectRole(role: UserRole): void {
    this.selectedRole.set(role);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Fecha o modal só quando o clique foi direto no overlay
   * (não borbulhado do card) — substitui `stopPropagation()` no card
   * interno, que o linter de acessibilidade rejeitaria (handler de
   * clique sem par de teclado num elemento não focável).
   */
  protected onOverlayClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.closeModal.emit();
    }
  }

  protected confirm(): void {
    this.confirmRole.emit(this.selectedRole());
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Clique no toggle de acesso de teste — emite o estado
   * oposto ao atual, o pai decide se confirma direto ou pede
   * confirmação extra antes de chamar a API.
   */
  protected onToggleTestAccess(): void {
    this.toggleTestAccess.emit(!this.user().is_admin_test_access);
  }
}
