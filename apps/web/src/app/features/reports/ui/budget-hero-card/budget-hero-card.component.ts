import { Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Card de destaque "Teto de gastos do período" no topo do
 * Dashboard — Despesas realizadas / Teto mensal / Status lado a lado,
 * barra de progresso e nota textual, replicando o card equivalente do
 * irmão em `/home/adriano/Documentos/projetos/Amezia`
 * (`dash__hero-card`), que tinha ficado de fora da 1ª versão desta
 * sessão (só os 4 cards pequenos foram trazidos) — pedido explícito do
 * usuário em 2026-08-15 depois de comparar com o irmão. Sem "R$" nos
 * valores monetários, ao contrário do irmão: mantém a convenção já
 * estabelecida do projeto (`BrlAmountPipe`).
 */
@Component({
  selector: 'app-budget-hero-card',
  standalone: true,
  imports: [TranslocoModule, RouterLink, BrlAmountPipe],
  templateUrl: './budget-hero-card.component.html',
  styleUrl: './budget-hero-card.component.css',
})
export class BudgetHeroCardComponent {
  totalExpense = input.required<string>();
  budgetLimit = input<string | null>(null);
  periodLabel = input.required<string>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: `budgetLimit()` convertido pra número, só quando é um
   * teto de verdade (> 0) — `null` (sem teto configurado) controla o
   * estado "Cadastre o teto" do card.
   */
  protected readonly budgetValue = computed(() => {
    const parsed = Number(this.budgetLimit());
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: `totalExpense()` convertido pra número.
   */
  protected readonly expenseValue = computed(() => Number(this.totalExpense()) || 0);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Percentual do teto já consumido — `null` sem teto
   * configurado.
   */
  protected readonly usagePercent = computed(() => {
    const budget = this.budgetValue();
    return budget === null ? null : (this.expenseValue() / budget) * 100;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Diferença entre teto e despesas — negativa quando o
   * teto foi ultrapassado. `null` sem teto configurado.
   */
  protected readonly difference = computed(() => {
    const budget = this.budgetValue();
    return budget === null ? null : budget - this.expenseValue();
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: `true` quando as despesas já ultrapassaram o teto —
   * controla a cor do "Status" e da barra de progresso.
   */
  protected readonly isOverBudget = computed(() => (this.difference() ?? 0) < 0);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Largura (0–100) da barra de progresso — nunca
   * ultrapassa 100% visualmente, mesmo com o teto estourado.
   */
  protected readonly barWidth = computed(() => {
    const usage = this.usagePercent();
    return usage === null ? 0 : Math.min(Math.max(usage, 0), 100);
  });
}
