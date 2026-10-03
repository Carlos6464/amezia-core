import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import type { ReportTransaction } from '@amezia/shared-types';

import { BrDatePipe } from '../../../../shared/pipes/br-date.pipe';
import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Preview das 5 transações mais recentes do mês selecionado
 * (Dashboard) + link "ver todas as despesas", que navega para o módulo
 * de Transações — build-context-05 §3.3. O ponto colorido de cada linha
 * usa a cor neutra do accent (não a cor real da categoria): a resposta
 * de `GET /reports/transactions` só traz `category_name`, não `color`
 * — replicar a cor por categoria do protótipo exigiria uma 2ª chamada
 * só para isso.
 */
@Component({
  selector: 'app-recent-transactions-list',
  standalone: true,
  imports: [RouterLink, TranslocoModule, BrDatePipe, BrlAmountPipe],
  templateUrl: './recent-transactions-list.component.html',
  styleUrl: './recent-transactions-list.component.css',
})
export class RecentTransactionsListComponent {
  transactions = input.required<ReportTransaction[]>();
}
