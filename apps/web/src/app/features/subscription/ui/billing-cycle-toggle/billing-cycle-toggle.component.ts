import { Component, input, output } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';
import type { BillingCycle } from '@amezia/shared-types';

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Switch "burro" Mensal/Anual (build-context-09 §3.2, T16)
 * — reaproveitado por `register-plan-page`/`settings-plans-page`.
 * Quando `annualAvailable()` é `false` (nenhum preço anual cadastrado
 * ainda pelo Admin), o switch fica travado em "Mensal" e mostra "em
 * breve" no lugar do selo de desconto — nunca deixa o usuário escolher
 * um ciclo sem preço real por trás.
 */
@Component({
  selector: 'app-billing-cycle-toggle',
  standalone: true,
  imports: [TranslocoModule],
  templateUrl: './billing-cycle-toggle.component.html',
  styleUrl: './billing-cycle-toggle.component.css',
})
export class BillingCycleToggleComponent {
  readonly value = input.required<BillingCycle>();
  readonly annualAvailable = input(false);

  readonly valueChange = output<BillingCycle>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Alterna mensal/anual — ignora o clique por completo
   * quando o anual ainda não está disponível.
   */
  toggle(): void {
    if (!this.annualAvailable()) {
      return;
    }
    this.valueChange.emit(this.value() === 'monthly' ? 'annual' : 'monthly');
  }
}
