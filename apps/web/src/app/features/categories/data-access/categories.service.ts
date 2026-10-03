import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import type { Category, CategoryCreateRequest, CategoryUpdateRequest } from '@amezia/shared-types';
import { Observable, tap } from 'rxjs';

const BASE_URL = '/api/v1/categories';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-09
 * Descrição: Estado das categorias (globais + privadas) via Signals —
 * dataset pequeno (7 globais + privadas do usuário, sem limite de
 * quantidade), sem cache complexo. Chama o HttpClient diretamente (sem um
 * data-access de API separado, diferente do módulo Auth) porque não há
 * orquestração adicional além de refletir a resposta do backend nos
 * Signals locais.
 */
@Injectable({ providedIn: 'root' })
export class CategoriesService {
  private readonly http = inject(HttpClient);

  readonly categories = signal<Category[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Subconjunto de `categories()` visível a todos os usuários
   * (`scope === 'global'`) — as 7 categorias de sistema.
   */
  readonly globalCategories = computed(() =>
    this.categories().filter((category) => category.scope === 'global'),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Subconjunto de `categories()` que pertence só ao usuário
   * autenticado (`scope === 'private'`).
   */
  readonly privateCategories = computed(() =>
    this.categories().filter((category) => category.scope === 'private'),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-09
   * Descrição: Quantidade atual de categorias privadas — usado para
   * exibir no stats-strip (sem limite de quantidade desde 2026-09-09).
   */
  readonly privateCount = computed(() => this.privateCategories().length);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Categoria com mais transações — alimenta o card "Mais
   * usada" do stats-strip (Uso/Movimentado real desde 2026-08-11; antes
   * disso era placeholder "—", à espera de Transações existir —
   * Observação 2 do build-context-02). `null` enquanto nenhuma
   * categoria tem transação nenhuma (`transaction_count === 0` em
   * todas). Em empate de contagem, fica a primeira encontrada — sem
   * critério de desempate explícito, não foi pedido.
   */
  readonly mostUsedCategory = computed<Category | null>(() => {
    const categories = this.categories();
    return categories.reduce<Category | null>((mostUsed, category) => {
      if (category.transaction_count === 0) {
        return mostUsed;
      }
      if (!mostUsed || category.transaction_count > mostUsed.transaction_count) {
        return category;
      }
      return mostUsed;
    }, null);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Carrega a listagem completa (globais + privadas do
   * usuário autenticado) — chamado pela página no ngOnInit.
   */
  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.http.get<Category[]>(BASE_URL).subscribe({
      next: (categories) => {
        this.categories.set(categories);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('categories.errors.loadFailed');
        this.loading.set(false);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Cria uma categoria privada e a acrescenta ao Signal local
   * em caso de sucesso — quem chama decide o que fazer com o erro (ex.:
   * mostrar mensagem no form-dialog).
   */
  create(payload: CategoryCreateRequest): Observable<Category> {
    return this.http
      .post<Category>(BASE_URL, payload)
      .pipe(tap((category) => this.categories.update((current) => [...current, category])));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Atualiza name/color de uma categoria privada e sincroniza
   * o Signal local com a resposta do backend. `transaction_count`/
   * `total_amount` da resposta do `PATCH` sempre vêm zerados (o backend
   * não recalcula uso num update — `CategoryResponse.from_entity`, ver
   * `apps/api/.../categories/schemas.py`); editar nome/cor/ícone não
   * muda quantas transações a categoria tem, então preserva os valores
   * de uso já carregados localmente em vez de confiar na resposta.
   */
  update(publicId: string, payload: CategoryUpdateRequest): Observable<Category> {
    return this.http.patch<Category>(`${BASE_URL}/${publicId}`, payload).pipe(
      tap((updated) =>
        this.categories.update((current) =>
          current.map((category) =>
            category.public_id === publicId
              ? {
                  ...updated,
                  transaction_count: category.transaction_count,
                  total_amount: category.total_amount,
                }
              : category,
          ),
        ),
      ),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Remove uma categoria privada e a retira do Signal local.
   */
  remove(publicId: string): Observable<void> {
    return this.http.delete<void>(`${BASE_URL}/${publicId}`).pipe(
      tap(() =>
        this.categories.update((current) =>
          current.filter((category) => category.public_id !== publicId),
        ),
      ),
    );
  }
}
