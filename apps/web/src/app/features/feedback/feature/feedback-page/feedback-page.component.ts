import { Component, computed, inject, signal } from '@angular/core';
import type { FeedbackType } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

import { AuthService } from '../../../../core/auth/auth.service';
import { FeedbackService } from '../../data-access/feedback.service';
import { FeedbackFormComponent } from '../../ui/feedback-form/feedback-form.component';
import { FeedbackHistoryListComponent } from '../../ui/feedback-history-list/feedback-history-list.component';
import { FeedbackSuccessComponent } from '../../ui/feedback-success/feedback-success.component';
import { FeedbackTypeChipsComponent } from '../../ui/feedback-type-chips/feedback-type-chips.component';
import { NpsScaleComponent } from '../../ui/nps-scale/nps-scale.component';

type FeedbackTab = 'send' | 'history';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-16
 * Descrição: Página "Feedback" (build-context-08 §3.1) — smart
 * component, orquestra as abas "Enviar feedback"/"Histórico" e o estado
 * de NPS/tipo (que vive aqui, não nos componentes burros de seleção,
 * já que os dois entram juntos no mesmo payload de envio).
 */
@Component({
  selector: 'app-feedback-page',
  standalone: true,
  imports: [
    TranslocoModule,
    NpsScaleComponent,
    FeedbackTypeChipsComponent,
    FeedbackFormComponent,
    FeedbackSuccessComponent,
    FeedbackHistoryListComponent,
  ],
  templateUrl: './feedback-page.component.html',
  styleUrl: './feedback-page.component.css',
})
export class FeedbackPageComponent {
  protected readonly feedbackService = inject(FeedbackService);
  private readonly authService = inject(AuthService);

  protected readonly activeTab = signal<FeedbackTab>('send');
  protected readonly selectedNps = signal<number | null>(null);
  protected readonly selectedType = signal<FeedbackType>('praise');

  protected readonly userName = computed(() => this.authService.currentUser()?.name ?? null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Troca de aba — carrega o histórico sob demanda só na
   * primeira vez que a aba "Histórico" é aberta (`historyLoaded` evita
   * chamada desnecessária em trocas seguintes).
   */
  protected switchTab(tab: FeedbackTab): void {
    this.activeTab.set(tab);
    if (tab === 'history' && !this.feedbackService.historyLoaded()) {
      this.feedbackService.loadHistory();
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Monta o payload com NPS/tipo (estado desta página) +
   * assunto/mensagem (emitidos pelo `feedback-form`) e envia.
   */
  protected onSubmit(fields: { subject: string; message: string }): void {
    this.feedbackService.submit({
      message: fields.message,
      type: this.selectedType(),
      nps_score: this.selectedNps() ?? undefined,
      subject: fields.subject || undefined,
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Reseta o form para um novo envio — volta `submitted` e
   * limpa NPS/tipo escolhidos (mesmo estado inicial da aba).
   */
  protected onResetForm(): void {
    this.feedbackService.resetForm();
    this.selectedNps.set(null);
    this.selectedType.set('praise');
  }
}
