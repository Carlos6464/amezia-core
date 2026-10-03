import { Component, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { Transaction } from '@amezia/shared-types';

import { BrDatePipe } from '../../../../shared/pipes/br-date.pipe';
import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import { paymentMethodLabelKey } from '../../data-access/payment-method.model';
import { TransactionStatusBadgeComponent } from '../transaction-status-badge/transaction-status-badge.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Tabela desktop (>700px) + lista de cards mobile (≤700px) de
 * transações — mapeia `expenses/index.html`. Seleção de linhas alimenta
 * a exclusão em lote (ex.: todas as parcelas de uma compra, que
 * compartilham `installment.group_id`). Coluna "Tipo de pagamento"
 * (2026-09-15, fora de qualquer build-context, pedido direto do
 * usuário) reaproveita o mesmo `payment_method` que o formulário já
 * grava — só nunca tinha sido exibido na listagem.
 */
@Component({
  selector: 'app-transaction-table',
  standalone: true,
  imports: [TranslocoModule, TransactionStatusBadgeComponent, BrlAmountPipe, BrDatePipe],
  templateUrl: './transaction-table.component.html',
  styleUrl: './transaction-table.component.css',
})
export class TransactionTableComponent {
  transactions = input.required<Transaction[]>();
  selectedIds = input<ReadonlySet<string>>(new Set());

  pay = output<Transaction>();
  edit = output<Transaction>();
  remove = output<Transaction>();
  toggleSelect = output<string>();

  protected readonly paymentMethodLabelKey = paymentMethodLabelKey;
}
