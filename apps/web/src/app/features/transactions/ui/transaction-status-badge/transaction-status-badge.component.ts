import { Component, input } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { PaymentStatus } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Pílula de status de pagamento (Pendente/Pago) —
 * reaproveitada pela tabela, cards mobile e formulário.
 */
@Component({
  selector: 'app-transaction-status-badge',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './transaction-status-badge.component.html',
  styleUrl: './transaction-status-badge.component.css',
})
export class TransactionStatusBadgeComponent {
  status = input.required<PaymentStatus>();
}
