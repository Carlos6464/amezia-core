import { DatePipe } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { AdminPaymentsService } from '../../data-access/admin-payments.service';
import { StatCardComponent } from '../../ui/stat-card/stat-card.component';

const INTEGER_FORMATTER = new Intl.NumberFormat('pt-BR');

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-11
 * Descrição: Tela de Pagamentos do Admin (build-context-11 §3.2/T8) —
 * KPIs financeiros (MRR/ARR/churn/ticket médio), alerta de pagamentos
 * falhados, feed de eventos Stripe e tabela de pagamentos recentes,
 * todos vindos de `GET /admin/payments` — nunca chama a API do Stripe
 * do frontend.
 */
@Component({
  selector: 'app-admin-payments-page',
  standalone: true,
  imports: [TranslocoModule, StatCardComponent, BrlAmountPipe, DatePipe],
  templateUrl: './admin-payments-page.component.html',
  styleUrl: './admin-payments-page.component.css',
})
export class AdminPaymentsPageComponent implements OnInit {
  private readonly service = inject(AdminPaymentsService);

  protected readonly payments = this.service.payments;
  protected readonly loading = this.service.loading;
  protected readonly error = this.service.error;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Busca os dados da tela ao montar.
   */
  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Busca os KPIs financeiros + feeds ao montar a página.
   */
  ngOnInit(): void {
    this.service.load();
  }

  protected formatCount(value: number | undefined): string {
    return INTEGER_FORMATTER.format(value ?? 0);
  }
}
