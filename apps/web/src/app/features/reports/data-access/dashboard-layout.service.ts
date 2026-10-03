import { Injectable, inject, signal } from '@angular/core';
import type { DashboardCard, DashboardCardPreference } from '@amezia/shared-types';
import { Observable, finalize, map, tap } from 'rxjs';

import { DEFAULT_DASHBOARD_LAYOUT, mergeDashboardLayout } from './dashboard-layout.model';
import { ReportsApiService } from './reports-api.service';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-15
 * Descrição: Estado da personalização do Dashboard via Signals (pedido
 * direto do usuário, fora de qualquer build-context) — mesmo padrão de
 * `BudgetService` (serviço pequeno e dedicado, em vez de inchar
 * `ReportsStateService` com uma preferência de UI que só o Dashboard
 * usa). `layout()` já vem mesclado com o padrão (`mergeDashboardLayout`)
 * — quem consome nunca precisa checar `null`. O painel de
 * personalização (`customizeModalVisible`/`customizeDraft` e o resto do
 * estado abaixo) também mora aqui, não em `DashboardPageComponent` —
 * precisa ser aberto pelo botão "Personalizar" do topbar global
 * (`AppShellComponent`, sempre montado), que não é filho/pai do
 * componente da página, então só um serviço `providedIn: 'root'`
 * compartilhado consegue ligar os dois (correção de 2026-09-15: a 1ª
 * versão tinha esse estado local na página, e o botão só existia
 * dentro do cabeçalho da própria página do Dashboard).
 */
@Injectable({ providedIn: 'root' })
export class DashboardLayoutService {
  private readonly api = inject(ReportsApiService);

  readonly layout = signal<DashboardCardPreference[]>(DEFAULT_DASHBOARD_LAYOUT);
  readonly loading = signal(false);
  readonly saving = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Carrega o layout salvo do usuário — chamado uma vez ao
   * abrir o Dashboard (`DashboardPageComponent.ngOnInit`).
   */
  load(): void {
    this.loading.set(true);
    this.api.getDashboardLayout().subscribe({
      next: (response) => {
        this.layout.set(mergeDashboardLayout(response.layout));
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Salva o layout completo (visibilidade + ordem dos 6
   * cards) — chamado pelo botão "Salvar" do painel de personalização.
   * Atualiza o Signal local com a resposta do backend (não com o
   * `layout` enviado), mesmo padrão de `changeRole`/`setTestAccess` já
   * usados no projeto: a fonte de verdade pós-escrita é sempre a
   * resposta do servidor.
   */
  save(layout: DashboardCardPreference[]): Observable<DashboardCardPreference[]> {
    this.saving.set(true);
    return this.api.updateDashboardLayout(layout).pipe(
      map((response) => mergeDashboardLayout(response.layout)),
      tap((merged) => this.layout.set(merged)),
      finalize(() => this.saving.set(false)),
    );
  }

  readonly customizeModalVisible = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Rascunho local do layout, editado dentro do painel de
   * personalização — só vira o layout de verdade (`layout()`) ao clicar
   * "Salvar"; "Cancelar" descarta sem chamar a API.
   */
  readonly customizeDraft = signal<DashboardCardPreference[]>([]);
  private draggedIndex: number | null = null;
  readonly dragOverIndex = signal<number | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Abre o painel de personalização, copiando o layout atual
   * pro rascunho — nunca edita `layout()` diretamente (evitaria
   * refletir mudanças não salvas na tela por trás do painel). Chamado
   * tanto pelo botão do topbar global (`AppShellComponent`) quanto por
   * qualquer outro gatilho futuro dentro do próprio Dashboard.
   */
  openCustomizeModal(): void {
    this.customizeDraft.set(this.layout().map((preference) => ({ ...preference })));
    this.customizeModalVisible.set(true);
  }

  closeCustomizeModal(): void {
    this.customizeModalVisible.set(false);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Liga/desliga a visibilidade de um card no rascunho — não
   * mexe na posição dele na lista.
   */
  toggleCardVisibility(card: DashboardCard): void {
    this.customizeDraft.update((list) =>
      list.map((preference) =>
        preference.card === card ? { ...preference, visible: !preference.visible } : preference,
      ),
    );
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Arrastar-pra-reordenar via Pointer Events (mouse + toque
   * no mesmo conjunto de eventos, GUIA_TECNICO §14.4) — `pointerdown` na
   * alça guarda o índice de origem e captura o ponteiro
   * (`setPointerCapture`), pra `pointermove`/`pointerup` continuarem
   * chegando na própria alça mesmo que o dedo/cursor saia dela.
   */
  onPointerDown(event: PointerEvent, index: number): void {
    event.preventDefault();
    this.draggedIndex = index;
    this.dragOverIndex.set(index);
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Reordena o rascunho em tempo real enquanto arrasta —
   * `elementFromPoint` acha o item sob o ponteiro (a alça capturou o
   * ponteiro, então `event.target` continua sendo sempre a alça de
   * origem; é por isso que a posição precisa ser lida via coordenada).
   */
  onPointerMove(event: PointerEvent): void {
    if (this.draggedIndex === null) {
      return;
    }
    event.preventDefault();
    const target = document
      .elementFromPoint(event.clientX, event.clientY)
      ?.closest('.customize-item') as HTMLElement | null;
    if (!target) {
      return;
    }
    const targetIndex = Number(target.dataset['index']);
    if (Number.isNaN(targetIndex) || targetIndex === this.draggedIndex) {
      return;
    }
    this.dragOverIndex.set(targetIndex);
    const fromIndex = this.draggedIndex;
    this.customizeDraft.update((list) => {
      const copy = [...list];
      const [moved] = copy.splice(fromIndex, 1);
      copy.splice(targetIndex, 0, moved);
      return copy;
    });
    this.draggedIndex = targetIndex;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Encerra o arraste (`pointerup`/`pointercancel`) — a
   * reordenação já aconteceu em tempo real em `onPointerMove`, então só
   * limpa o estado visual/de controle.
   */
  onPointerUp(): void {
    this.draggedIndex = null;
    this.dragOverIndex.set(null);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Salva o rascunho — o painel só fecha depois da resposta
   * do backend confirmar (mesmo padrão de `confirmToggleTestAccess` do
   * Admin: nunca fecha otimisticamente antes de saber que salvou).
   */
  saveCustomization(): void {
    this.save(this.customizeDraft()).subscribe({
      next: () => this.customizeModalVisible.set(false),
    });
  }
}
