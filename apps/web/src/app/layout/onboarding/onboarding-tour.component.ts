import { NgStyle } from '@angular/common';
import { Component, HostListener, effect, inject, signal } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

import { OnboardingService } from './onboarding.service';

interface SpotlightRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const SPOTLIGHT_PADDING = 8;
const TOOLTIP_WIDTH = 320;
const GAP = 16;
const MEASURE_DELAY_MS = 120;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Tour guiado com spotlight (build-context fora do escopo
 * original, estratégia validada replicando o padrão já usado no projeto
 * irmão) — overlay escuro com um "buraco" iluminado sobre o elemento
 * real da UI (`[data-tour="..."]`), via `box-shadow` gigante em vez de
 * clip-path/mask (mesmo truque do irmão). Sem lib de terceiros.
 */
@Component({
  selector: 'app-onboarding-tour',
  standalone: true,
  imports: [TranslocoModule, NgStyle],
  templateUrl: './onboarding-tour.component.html',
  styleUrl: './onboarding-tour.component.css',
})
export class OnboardingTourComponent {
  protected readonly onboarding = inject(OnboardingService);

  protected readonly spotlightRect = signal<SpotlightRect | null>(null);
  protected readonly tooltipStyle = signal<Record<string, string>>({});

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Remede o spotlight/tooltip sempre que o tour abre ou o
   * passo muda — o `setTimeout` espera o layout assentar (ex.: troca de
   * aba/scroll) antes de medir `getBoundingClientRect()`, mesmo padrão
   * do irmão.
   */
  constructor() {
    effect(() => {
      const open = this.onboarding.tourOpen();
      this.onboarding.tourStep();
      if (open) {
        setTimeout(() => this.measure(), MEASURE_DELAY_MS);
      }
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Reage a resize da janela pra reposicionar spotlight e
   * tooltip enquanto o tour está aberto.
   */
  @HostListener('window:resize')
  onWindowResize(): void {
    if (this.onboarding.tourOpen()) {
      this.measure();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Localiza o elemento-alvo do passo atual e calcula
   * spotlight+tooltip. Sem o elemento (ex.: sidebar escondida no
   * mobile) ou com largura zero, cai no tooltip centralizado — nunca
   * quebra o tour por um alvo ausente.
   */
  private measure(): void {
    const step = this.onboarding.currentTourStep();
    if (!step) {
      this.spotlightRect.set(null);
      return;
    }

    const element = document.querySelector<HTMLElement>(step.target);
    const rect = element?.getBoundingClientRect();

    if (!rect || rect.width === 0) {
      this.spotlightRect.set(null);
      this.tooltipStyle.set(this.centeredTooltipStyle());
      return;
    }

    this.spotlightRect.set({
      top: rect.top - SPOTLIGHT_PADDING,
      left: rect.left - SPOTLIGHT_PADDING,
      width: rect.width + SPOTLIGHT_PADDING * 2,
      height: rect.height + SPOTLIGHT_PADDING * 2,
    });
    this.tooltipStyle.set(this.calcTooltipStyle(rect, step.position));
  }

  private calcTooltipStyle(
    rect: DOMRect,
    position: 'top' | 'bottom' | 'left' | 'right',
  ): Record<string, string> {
    const maxLeft = window.innerWidth - TOOLTIP_WIDTH - 16;
    switch (position) {
      case 'right':
        return { top: `${Math.max(16, rect.top)}px`, left: `${Math.min(rect.right + GAP, maxLeft)}px` };
      case 'left':
        return { top: `${Math.max(16, rect.top)}px`, left: `${Math.max(16, rect.left - TOOLTIP_WIDTH - GAP)}px` };
      case 'bottom':
        return { top: `${rect.bottom + GAP}px`, left: `${Math.min(Math.max(16, rect.left), maxLeft)}px` };
      case 'top':
        return { top: `${Math.max(16, rect.top - GAP)}px`, left: `${Math.min(Math.max(16, rect.left), maxLeft)}px`, transform: 'translateY(-100%)' };
    }
  }

  private centeredTooltipStyle(): Record<string, string> {
    return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };
  }

  protected onNext(): void {
    this.onboarding.nextStep();
  }

  protected onPrev(): void {
    this.onboarding.prevStep();
  }

  protected onSkip(): void {
    this.onboarding.skipTour();
  }
}
