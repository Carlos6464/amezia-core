import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AdminUser, UserRole } from '@amezia/shared-types';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ConfirmDialogModule } from 'primeng/confirmdialog';

import { AdminUsersService } from '../../data-access/admin-users.service';
import { ChangeRoleModalComponent } from '../../ui/change-role-modal/change-role-modal.component';
import { PaginationComponent } from '../../ui/pagination/pagination.component';
import { UsersTableComponent } from '../../ui/users-table/users-table.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Tela Usuários do Admin (build-context-06 §3.3) — tabela
 * paginada com busca por nome/e-mail e filtro por papel; clique na
 * linha abre o modal de troca de papel. Desde 2026-09-15, também
 * exibe o badge "Teste" (acesso Premium vitalício concedido pelo
 * admin, sem Stripe) e o toggle correspondente no modal — pedido
 * direto do usuário, fora de qualquer build-context. Escopo reduzido
 * do protótipo, o resto continua de fora: sem uso de IA na própria
 * tela, sem impersonar/suspender (nenhum tem regra de negócio no
 * MVP1).
 */
@Component({
  selector: 'app-admin-users-page',
  standalone: true,
  imports: [
    FormsModule,
    TranslocoModule,
    ConfirmDialogModule,
    UsersTableComponent,
    PaginationComponent,
    ChangeRoleModalComponent,
  ],
  templateUrl: './admin-users-page.component.html',
  styleUrl: './admin-users-page.component.css',
})
export class AdminUsersPageComponent implements OnInit {
  private readonly usersService = inject(AdminUsersService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);

  readonly users = this.usersService.users;
  readonly loading = this.usersService.loading;
  readonly error = this.usersService.error;
  readonly filters = this.usersService.filters;
  readonly pagination = this.usersService.pagination;

  protected readonly searchTerm = signal('');
  protected readonly selectedUser = signal<AdminUser | null>(null);
  protected readonly savingRole = signal(false);
  protected readonly savingTestAccess = signal(false);

  ngOnInit(): void {
    this.usersService.load();
  }

  protected onSearchChange(value: string): void {
    this.searchTerm.set(value);
    this.usersService.updateFilters({ search: value });
  }

  protected onRoleFilterChange(value: string): void {
    this.usersService.updateFilters({ role: (value as UserRole | '') || '' });
  }

  protected onPageChange(page: number): void {
    this.usersService.updateFilters({ page });
  }

  protected openChangeRole(user: AdminUser): void {
    this.selectedUser.set(user);
  }

  protected closeChangeRole(): void {
    this.selectedUser.set(null);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Confirma a troca de papel e fecha o modal em caso de
   * sucesso — a listagem local já é atualizada pelo próprio
   * AdminUsersService.changeRole(). Toast de sucesso/erro
   * (build-context-13) — antes essa ação ficava muda nos dois casos.
   */
  protected confirmChangeRole(role: UserRole): void {
    const user = this.selectedUser();
    if (!user) {
      return;
    }
    this.savingRole.set(true);
    this.usersService.changeRole(user.id, role).subscribe({
      next: () => {
        this.savingRole.set(false);
        this.selectedUser.set(null);
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('toasts.successTitle'),
          detail: this.transloco.translate('toasts.admin.roleChanged'),
        });
      },
      error: () => {
        this.savingRole.set(false);
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('toasts.errorTitle'),
          detail: this.transloco.translate('toasts.admin.roleChangeError'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Concede/revoga o acesso de teste — salva na hora (sem
   * depender do botão "Salvar" do papel) e mantém o modal aberto,
   * atualizando o Signal local pro switch refletir o novo estado.
   */
  protected confirmToggleTestAccess(enabled: boolean): void {
    const user = this.selectedUser();
    if (!user) {
      return;
    }
    this.savingTestAccess.set(true);
    this.usersService.setTestAccess(user.id, enabled).subscribe({
      next: (updated) => {
        this.savingTestAccess.set(false);
        this.selectedUser.set(updated);
      },
      error: () => {
        this.savingTestAccess.set(false);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Abre o `ConfirmDialog` do PrimeNG antes de excluir uma
   * conta — a exclusão de verdade (`DELETE /admin/users/{id}`) só
   * acontece se o admin confirmar (`accept`), mesmo padrão de
   * `confirmDelete` em CategoriesListComponent. Fora de qualquer
   * build-context — pedido direto do usuário pra remover contas de
   * teste/debug esquecidas em produção.
   */
  protected confirmDeleteUser(user: AdminUser): void {
    this.confirmationService.confirm({
      header: this.transloco.translate('admin.users.confirmDelete.header'),
      message: this.transloco.translate('admin.users.confirmDelete.message', { email: user.email }),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: this.transloco.translate('admin.users.confirmDelete.accept'),
      rejectLabel: this.transloco.translate('admin.users.confirmDelete.reject'),
      acceptButtonProps: { severity: 'danger' },
      rejectButtonProps: { severity: 'secondary', outlined: true },
      accept: () => this.deleteUser(user),
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Chama `AdminUsersService.deleteUser` (que já remove o
   * usuário da listagem local em caso de sucesso) e mostra um toast de
   * confirmação ou erro.
   */
  private deleteUser(user: AdminUser): void {
    this.usersService.deleteUser(user.id).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('admin.users.confirmDelete.toastTitle'),
          detail: this.transloco.translate('admin.users.confirmDelete.success', { email: user.email }),
        });
      },
      error: () => {
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('admin.users.confirmDelete.toastTitle'),
          detail: this.transloco.translate('admin.users.confirmDelete.errorGeneric'),
        });
      },
    });
  }
}
