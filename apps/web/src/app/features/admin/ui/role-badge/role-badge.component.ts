import { Component, input } from '@angular/core';
import type { UserRole } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Badge de papel (`user`/`admin`) reaproveitado pela tabela
 * de usuários e pelo modal de troca de papel (build-context-06 §3.1).
 */
@Component({
  selector: 'app-role-badge',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './role-badge.component.html',
  styleUrl: './role-badge.component.css',
})
export class RoleBadgeComponent {
  readonly role = input.required<UserRole>();
}
