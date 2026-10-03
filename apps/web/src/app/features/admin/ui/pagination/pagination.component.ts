import { Component, input, output } from '@angular/core';
import type { PaginationInfo } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Paginador genérico do módulo Admin (build-context-06 §3.1)
 * — componente único reaproveitado pela tela Usuários e pela tela
 * Feedback, recebendo o `PaginationInfo` já resolvido pelo backend.
 */
@Component({
  selector: 'app-admin-pagination',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './pagination.component.html',
  styleUrl: './pagination.component.css',
})
export class PaginationComponent {
  readonly pagination = input.required<PaginationInfo>();
  readonly pageChange = output<number>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Emite a nova página quando dentro do intervalo válido —
   * ignora silenciosamente cliques fora dos limites (botões já vêm
   * `disabled` nesses casos, isto é só a segunda linha de defesa).
   */
  goToPage(page: number): void {
    if (page < 1 || page > this.pagination().total_pages) {
      return;
    }
    this.pageChange.emit(page);
  }
}
