import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AdminFeedback, FeedbackChannel } from '@amezia/shared-types';
import { TranslocoModule } from '@jsverse/transloco';

import { AdminFeedbackService } from '../../data-access/admin-feedback.service';
import { FeedbackCardComponent } from '../../ui/feedback-card/feedback-card.component';
import { FeedbackDetailModalComponent } from '../../ui/feedback-detail-modal/feedback-detail-modal.component';
import { PaginationComponent } from '../../ui/pagination/pagination.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Tela Feedback do Admin (build-context-06 §3.3/§2.9) —
 * lista paginada de feedback-card, busca por texto e filtro por canal;
 * reaproveita o `pagination/` genérico da tela Usuários. Escopo
 * reduzido do protótipo: sem NPS/tipo/assunto/"responder por
 * email"/"marcar como lido" (não existem no modelo de dados do MVP1,
 * PRD §6.9 — ver decisão registrada no build-context-08).
 */
@Component({
  selector: 'app-admin-feedback-page',
  standalone: true,
  imports: [FormsModule, TranslocoModule, FeedbackCardComponent, PaginationComponent, FeedbackDetailModalComponent],
  templateUrl: './admin-feedback-page.component.html',
  styleUrl: './admin-feedback-page.component.css',
})
export class AdminFeedbackPageComponent implements OnInit {
  private readonly feedbackService = inject(AdminFeedbackService);

  readonly feedback = this.feedbackService.feedback;
  readonly loading = this.feedbackService.loading;
  readonly error = this.feedbackService.error;
  readonly filters = this.feedbackService.filters;
  readonly pagination = this.feedbackService.pagination;

  protected readonly searchTerm = signal('');
  protected readonly selectedFeedback = signal<AdminFeedback | null>(null);

  ngOnInit(): void {
    this.feedbackService.load();
  }

  protected onSearchChange(value: string): void {
    this.searchTerm.set(value);
    this.feedbackService.updateFilters({ search: value });
  }

  protected onChannelFilterChange(value: string): void {
    this.feedbackService.updateFilters({ channel: (value as FeedbackChannel | '') || '' });
  }

  protected onPageChange(page: number): void {
    this.feedbackService.updateFilters({ page });
  }

  protected openDetail(item: AdminFeedback): void {
    this.selectedFeedback.set(item);
  }

  protected closeDetail(): void {
    this.selectedFeedback.set(null);
  }
}
