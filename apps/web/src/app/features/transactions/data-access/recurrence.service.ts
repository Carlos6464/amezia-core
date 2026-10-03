import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { RecurrenceRule } from '@amezia/shared-types';
import { Observable, tap } from 'rxjs';

const BASE_URL = '/api/v1/transactions/recurrences';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Gestão das regras de recorrência ativas do usuário
 * (build-context-03 §2.7) — sem tela dedicada; usado pelo banner
 * "gerada automaticamente por..." no formulário de edição de transação.
 */
@Injectable({ providedIn: 'root' })
export class RecurrenceService {
  private readonly http = inject(HttpClient);

  readonly recurrences = signal<RecurrenceRule[]>([]);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Carrega as regras de recorrência ativas do usuário.
   */
  load(): void {
    this.http.get<RecurrenceRule[]>(BASE_URL).subscribe((rules) => this.recurrences.set(rules));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Cancela (desativa) uma recorrência — não apaga as
   * transações já geradas por ela.
   */
  cancel(publicId: string): Observable<void> {
    return this.http
      .delete<void>(`${BASE_URL}/${publicId}`)
      .pipe(
        tap(() =>
          this.recurrences.update((current) => current.filter((r) => r.public_id !== publicId)),
        ),
      );
  }
}
