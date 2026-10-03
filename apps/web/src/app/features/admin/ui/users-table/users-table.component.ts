import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';
import type { AdminUser } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

import { RoleBadgeComponent } from '../role-badge/role-badge.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Tabela paginada de usuários (build-context-06 §3.3) — dumb
 * component, recebe a página atual já filtrada/paginada pelo backend.
 * Clique na linha abre o modal de detalhe/troca de papel (emitido pro
 * pai decidir).
 */
@Component({
  selector: 'app-users-table',
  standalone: true,
  imports: [TranslocoModule, DatePipe, RoleBadgeComponent],
  templateUrl: './users-table.component.html',
  styleUrl: './users-table.component.css',
})
export class UsersTableComponent {
  readonly users = input.required<AdminUser[]>();
  readonly total = input(0);
  readonly rowClick = output<AdminUser>();
  readonly deleteUser = output<AdminUser>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Emite `deleteUser` sem disparar o `rowClick` da linha
   * (que abre o modal de troca de papel) — o botão de excluir fica
   * dentro da mesma `<tr>`, então o clique precisa parar de propagar.
   */
  onDeleteClick(event: Event, user: AdminUser): void {
    event.stopPropagation();
    this.deleteUser.emit(user);
  }
}
