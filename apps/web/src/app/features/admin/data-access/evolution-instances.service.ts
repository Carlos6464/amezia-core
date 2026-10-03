import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type {
  AdminPaginatedResponse,
  EvolutionInstance,
  EvolutionInstanceCreateRequest,
  EvolutionInstanceUpdateRequest,
  PaginationInfo,
} from '@amezia/shared-types';
import { Observable, tap } from 'rxjs';

const BASE_URL = '/api/v1/admin/evolution-instances';

const EMPTY_PAGINATION: PaginationInfo = { page: 1, page_size: 20, total: 0, total_pages: 0 };

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Estado das instâncias Evolution via Signals (build-context-06
 * §3.3) — CRUD completo + connect/sync/disconnect, todos atualizando a
 * mesma listagem local em vez de recarregar a página inteira (importante
 * pro polling da tela WhatsApp não piscar a UI a cada tick).
 */
@Injectable({ providedIn: 'root' })
export class EvolutionInstancesService {
  private readonly http = inject(HttpClient);

  readonly instances = signal<EvolutionInstance[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly pagination = signal<PaginationInfo>(EMPTY_PAGINATION);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Lista paginada — MVP1 opera com no máximo uma instância
   * ativa por vez, então na prática a tela WhatsApp sempre lê
   * `instances()[0]`, mas a listagem em si já nasce paginada (§2.3).
   */
  load(page = 1, pageSize = 20): void {
    this.loading.set(true);
    this.error.set(null);
    const params = new HttpParams().set('page', page).set('page_size', pageSize);

    this.http.get<AdminPaginatedResponse<EvolutionInstance>>(BASE_URL, { params }).subscribe({
      next: (response) => {
        this.instances.set(response.items);
        this.pagination.set({
          page: response.page,
          page_size: response.page_size,
          total: response.total,
          total_pages: response.total_pages,
        });
        this.loading.set(false);
      },
      error: () => {
        this.error.set('admin.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: POST /admin/evolution-instances — recarrega a listagem
   * inteira após criar (a nova instância entra na paginação).
   */
  create(payload: EvolutionInstanceCreateRequest): Observable<EvolutionInstance> {
    return this.http
      .post<EvolutionInstance>(BASE_URL, payload)
      .pipe(tap(() => this.load(this.pagination().page, this.pagination().page_size)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: PATCH /admin/evolution-instances/{public_id} — usado
   * tanto para editar name/webhook_url quanto pra alternar `is_active`.
   */
  update(publicId: string, payload: EvolutionInstanceUpdateRequest): Observable<EvolutionInstance> {
    return this.http
      .patch<EvolutionInstance>(`${BASE_URL}/${publicId}`, payload)
      .pipe(tap((updated) => this._replace(updated)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: DELETE /admin/evolution-instances/{public_id}.
   */
  delete(publicId: string): Observable<void> {
    return this.http.delete<void>(`${BASE_URL}/${publicId}`).pipe(
      tap(() => {
        this.instances.update((list) => list.filter((item) => item.public_id !== publicId));
      }),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: POST .../connect — inicia o pareamento, devolve a
   * instância com `qr_code`/`status=connecting`.
   */
  connect(publicId: string): Observable<EvolutionInstance> {
    return this.http
      .post<EvolutionInstance>(`${BASE_URL}/${publicId}/connect`, {})
      .pipe(tap((updated) => this._replace(updated)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: POST .../sync — refresh manual de status/telefone.
   */
  sync(publicId: string): Observable<EvolutionInstance> {
    return this.http
      .post<EvolutionInstance>(`${BASE_URL}/${publicId}/sync`, {})
      .pipe(tap((updated) => this._replace(updated)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: POST .../disconnect — logout da sessão pareada.
   */
  disconnect(publicId: string): Observable<EvolutionInstance> {
    return this.http
      .post<EvolutionInstance>(`${BASE_URL}/${publicId}/disconnect`, {})
      .pipe(tap((updated) => this._replace(updated)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: GET /admin/evolution-instances/{public_id} — usado pelo
   * polling do `evolution-instance-card` enquanto `status=connecting`
   * (§3.3), sem recarregar a listagem inteira a cada tick.
   */
  getByPublicId(publicId: string): Observable<EvolutionInstance> {
    return this.http
      .get<EvolutionInstance>(`${BASE_URL}/${publicId}`)
      .pipe(tap((updated) => this._replace(updated)));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Substitui só o item atualizado dentro de `instances()`
   * (por public_id) — evita recarregar a listagem inteira a cada
   * connect/sync/disconnect/tick de polling.
   */
  private _replace(updated: EvolutionInstance): void {
    this.instances.update((list) =>
      list.map((item) => (item.public_id === updated.public_id ? updated : item)),
    );
  }
}
