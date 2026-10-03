import { Component, OnInit, computed, inject } from '@angular/core';
import { TranslocoModule } from '@jsverse/transloco';

import { AdminAiUsageService } from '../../data-access/admin-ai-usage.service';
import { StatCardComponent } from '../../ui/stat-card/stat-card.component';

const INTEGER_FORMATTER = new Intl.NumberFormat('pt-BR');
const CURRENCY_FORMATTER = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Overview de custo/uso de IA do Admin (build-context-10
 * §3.3) — KPIs de tokens/custo do mês corrente, quebra por feature e
 * por provider, e a tabela "por usuário" (top consumidores). Custo é
 * sempre estimado (tabela de preço em código, `pricing.py`) — nunca
 * saldo real de conta Google/xAI, texto explícito no template (§2.4 do
 * build-context-10).
 */
@Component({
  selector: 'app-admin-ai-usage-page',
  standalone: true,
  imports: [TranslocoModule, StatCardComponent],
  templateUrl: './admin-ai-usage-page.component.html',
  styleUrl: './admin-ai-usage-page.component.css',
})
export class AdminAiUsagePageComponent implements OnInit {
  private readonly service = inject(AdminAiUsageService);

  protected readonly overview = this.service.overview;
  protected readonly loading = this.service.loading;
  protected readonly error = this.service.error;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Soma tokens de entrada + saída de todos os eventos do
   * mês — usado no KPI "Tokens no mês".
   */
  protected readonly totalTokens = computed(() => {
    const overview = this.overview();
    return overview ? overview.total_input_tokens + overview.total_output_tokens : 0;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Quebra por feature já ordenada por custo (maior primeiro)
   * — a API não garante ordem nenhuma, a tela decide como exibir.
   */
  protected readonly byFeatureSorted = computed(() => {
    const overview = this.overview();
    if (!overview) {
      return [];
    }
    return [...overview.by_feature].sort((a, b) => b.estimated_cost_cents - a.estimated_cost_cents);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Busca o overview de uso/custo de IA ao montar a página.
   */
  ngOnInit(): void {
    this.service.load();
  }

  protected formatCount(value: number | undefined): string {
    return INTEGER_FORMATTER.format(value ?? 0);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Formata centavos (fracionários — a API não arredonda
   * mais pra inteiro, ver `_micros_to_cents` no backend) em BRL, com
   * até 4 casas decimais em vez das 2 padrão da moeda — o custo
   * estimado de uma única chamada de IA é uma fração de centavo, e
   * arredondar pra 2 casas aqui faria a quebra por feature/provider
   * mostrar R$0,00 de novo mesmo com custo real e não-zero registrado
   * (achado real, 2026-09-11).
   */
  protected formatCurrency(cents: number | undefined): string {
    return CURRENCY_FORMATTER.format((cents ?? 0) / 100);
  }
}
