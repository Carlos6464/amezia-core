import { Component, computed, inject } from '@angular/core';
import { Router } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import type { ChecklistItem } from './onboarding.model';
import { OnboardingService } from './onboarding.service';

const RING_RADIUS = 20;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: FAB com anel de progresso (SVG) + painel "Primeiros
 * passos" — mesma mecânica visual do projeto irmão. Ao contrário de
 * lá, dispensar o painel persiste de verdade (`OnboardingService.
 * dismissChecklist`, ver docstring lá).
 */
@Component({
  selector: 'app-onboarding-checklist',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './onboarding-checklist.component.html',
  styleUrl: './onboarding-checklist.component.css',
})
export class OnboardingChecklistComponent {
  protected readonly onboarding = inject(OnboardingService);
  private readonly router = inject(Router);

  protected readonly ringRadius = RING_RADIUS;
  protected readonly ringCircumference = RING_CIRCUMFERENCE;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: `stroke-dashoffset` do anel de progresso do FAB — quanto
   * mais itens concluídos, menor o offset (mais anel "preenchido").
   */
  protected readonly ringOffset = computed(() => {
    const total = this.onboarding.totalCount();
    const ratio = total > 0 ? this.onboarding.completedCount() / total : 0;
    return RING_CIRCUMFERENCE * (1 - ratio);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Clique num item do checklist — "concluir o tour" abre o
   * tour guiado; os demais navegam pra tela onde a ação acontece
   * (marcar como feito é responsabilidade de cada tela, no momento real
   * do sucesso, não daqui).
   */
  protected onItemClick(item: ChecklistItem): void {
    this.onboarding.checklistPanelOpen.set(false);
    if (item.id === 'tour') {
      this.onboarding.openTour();
      return;
    }
    if (item.route) {
      void this.router.navigateByUrl(item.route);
    }
  }

  protected onDismiss(): void {
    this.onboarding.dismissChecklist();
  }
}
