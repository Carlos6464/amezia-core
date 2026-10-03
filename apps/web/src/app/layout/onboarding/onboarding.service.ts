import { Injectable, computed, inject, signal } from '@angular/core';

import { AuthService } from '../../core/auth/auth.service';
import type { ChecklistItem, ChecklistItemId, TourStep } from './onboarding.model';

const STORAGE_DONE_KEY = 'amezia_onboarding_done';
const STORAGE_HIDDEN_KEY = 'amezia_onboarding_hidden';

const INITIAL_CHECKLIST: ChecklistItem[] = [
  {
    id: 'first_expense',
    labelKey: 'onboarding.checklist.items.firstExpense.label',
    route: '/transactions/new',
    done: false,
  },
  {
    id: 'category',
    labelKey: 'onboarding.checklist.items.category.label',
    route: '/categories',
    done: false,
  },
  {
    id: 'budget',
    labelKey: 'onboarding.checklist.items.budget.label',
    route: '/transactions',
    done: false,
  },
  {
    id: 'whatsapp',
    labelKey: 'onboarding.checklist.items.whatsapp.label',
    route: '/settings/profile',
    done: false,
  },
  {
    id: 'bot_number',
    labelKey: 'onboarding.checklist.items.botNumber.label',
    route: '/settings/profile',
    done: false,
  },
  {
    id: 'agent',
    labelKey: 'onboarding.checklist.items.agent.label',
    route: '/agent',
    done: false,
  },
  {
    id: 'tour',
    labelKey: 'onboarding.checklist.items.tour.label',
    route: null,
    done: false,
  },
];

const TOUR_STEPS: TourStep[] = [
  {
    target: '[data-tour="sidebar-dashboard"]',
    titleKey: 'onboarding.tour.steps.dashboard.title',
    descriptionKey: 'onboarding.tour.steps.dashboard.description',
    position: 'right',
  },
  {
    target: '[data-tour="sidebar-transactions"]',
    titleKey: 'onboarding.tour.steps.transactions.title',
    descriptionKey: 'onboarding.tour.steps.transactions.description',
    position: 'right',
  },
  {
    target: '[data-tour="sidebar-categories"]',
    titleKey: 'onboarding.tour.steps.categories.title',
    descriptionKey: 'onboarding.tour.steps.categories.description',
    position: 'right',
  },
  {
    target: '[data-tour="sidebar-reports"]',
    titleKey: 'onboarding.tour.steps.reports.title',
    descriptionKey: 'onboarding.tour.steps.reports.description',
    position: 'right',
  },
  {
    target: '[data-tour="sidebar-agent"]',
    titleKey: 'onboarding.tour.steps.agent.title',
    descriptionKey: 'onboarding.tour.steps.agent.description',
    position: 'right',
  },
  {
    target: '[data-tour="avatar-menu"]',
    titleKey: 'onboarding.tour.steps.settings.title',
    descriptionKey: 'onboarding.tour.steps.settings.description',
    position: 'bottom',
  },
];

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Estado do onboarding guiado (tour com spotlight + checklist
 * "Primeiros passos") via Signals — arquitetura replicada do projeto
 * irmão (`OnboardingService`), adaptada: `whatsapp`/`bot_number` são
 * itens novos (o irmão não tem nada equivalente), e os dois bugs de lá
 * foram corrigidos aqui: dispensar o checklist persiste de verdade
 * (`STORAGE_HIDDEN_KEY`, não só a sessão), e `resetOnboarding()` está
 * de fato ligado a um botão ("Reiniciar tour" em Configurações), não é
 * código morto.
 */
@Injectable({ providedIn: 'root' })
export class OnboardingService {
  private readonly authService = inject(AuthService);

  readonly tourSteps = TOUR_STEPS;

  readonly checklist = signal<ChecklistItem[]>(INITIAL_CHECKLIST);
  readonly checklistVisible = signal(false);
  readonly checklistPanelOpen = signal(false);

  readonly tourOpen = signal(false);
  readonly tourStep = signal(0);

  readonly completedCount = computed(() => this.checklist().filter((item) => item.done).length);
  readonly totalCount = computed(() => this.checklist().length);
  readonly allDone = computed(() => this.completedCount() === this.totalCount());

  readonly currentTourStep = computed<TourStep | null>(() => this.tourSteps[this.tourStep()] ?? null);
  readonly isLastTourStep = computed(() => this.tourStep() === this.tourSteps.length - 1);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Chamado uma vez no primeiro load do shell autenticado
   * (`AppShellComponent`). Se o backend já marca `onboarding_completed`,
   * não mostra nada. Senão, deriva o que já dá pra saber sem round-trip
   * extra (`phone` já vem no `currentUser`), carrega o progresso salvo em
   * `localStorage` e exibe o FAB — a menos que o usuário já tenha
   * dispensado antes (`STORAGE_HIDDEN_KEY`).
   */
  initForUser(): void {
    const user = this.authService.currentUser();
    if (!user || user.onboarding_completed) {
      this.checklistVisible.set(false);
      return;
    }

    if (user.phone) {
      this.markDoneLocal('whatsapp');
    }

    this.loadFromStorage();
    this.checklistVisible.set(localStorage.getItem(STORAGE_HIDDEN_KEY) !== 'true');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Marca um item como concluído (chamado pelos pontos reais
   * de sucesso de cada ação — criar transação/categoria, definir teto,
   * salvar telefone, visitar o Agente, clicar no link do bot, ou
   * terminar o tour) e persiste em `localStorage`. Quando todos os itens
   * ficam concluídos, sincroniza `onboarding_completed=true` no backend.
   */
  markDone(id: ChecklistItemId): void {
    if (!this.markDoneLocal(id)) {
      return;
    }
    this.saveToStorage();
    if (this.allDone()) {
      this.completeOnBackend();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Versão sem persistência de `markDone` — usada tanto pelo
   * método público quanto por `initForUser` (que já persiste tudo de
   * uma vez ao final, sem precisar gravar item a item). Devolve `true`
   * só quando o item existia e ainda não estava concluído (evita
   * `saveToStorage`/checagem de `allDone` à toa).
   */
  private markDoneLocal(id: ChecklistItemId): boolean {
    let changed = false;
    this.checklist.update((items) =>
      items.map((item) => {
        if (item.id === id && !item.done) {
          changed = true;
          return { ...item, done: true };
        }
        return item;
      }),
    );
    return changed;
  }

  openTour(): void {
    this.tourStep.set(0);
    this.tourOpen.set(true);
    this.checklistPanelOpen.set(false);
  }

  nextStep(): void {
    if (this.isLastTourStep()) {
      this.finishTour();
      return;
    }
    this.tourStep.update((step) => step + 1);
  }

  prevStep(): void {
    this.tourStep.update((step) => Math.max(0, step - 1));
  }

  skipTour(): void {
    this.tourOpen.set(false);
  }

  finishTour(): void {
    this.tourOpen.set(false);
    this.markDone('tour');
  }

  toggleChecklistPanel(): void {
    this.checklistPanelOpen.update((open) => !open);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Dispensa o FAB — diferente do projeto irmão (onde isso
   * não persistia e o FAB voltava a cada F5), aqui fica salvo em
   * `localStorage` até o usuário reiniciar o onboarding de propósito.
   */
  dismissChecklist(): void {
    this.checklistVisible.set(false);
    this.checklistPanelOpen.set(false);
    localStorage.setItem(STORAGE_HIDDEN_KEY, 'true');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: "Reiniciar tour" (Configurações) — zera o progresso local
   * e o backend, e reexibe o FAB. Diferente do projeto irmão, onde o
   * método equivalente existe mas não está ligado a nenhum botão real.
   */
  resetOnboarding(): void {
    this.checklist.set(INITIAL_CHECKLIST.map((item) => ({ ...item })));
    localStorage.removeItem(STORAGE_DONE_KEY);
    localStorage.removeItem(STORAGE_HIDDEN_KEY);
    this.checklistVisible.set(true);
    this.authService.updateOnboarding({ onboarding_completed: false }).subscribe();
  }

  private completeOnBackend(): void {
    this.authService.updateOnboarding({ onboarding_completed: true }).subscribe();
  }

  private loadFromStorage(): void {
    const raw = localStorage.getItem(STORAGE_DONE_KEY);
    if (!raw) {
      return;
    }
    const doneIds = new Set<string>(JSON.parse(raw) as string[]);
    this.checklist.update((items) =>
      items.map((item) => (doneIds.has(item.id) ? { ...item, done: true } : item)),
    );
  }

  private saveToStorage(): void {
    const doneIds = this.checklist()
      .filter((item) => item.done)
      .map((item) => item.id);
    localStorage.setItem(STORAGE_DONE_KEY, JSON.stringify(doneIds));
  }
}
