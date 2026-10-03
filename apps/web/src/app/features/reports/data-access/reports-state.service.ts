import { Injectable, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { TranslocoService } from '@jsverse/transloco';
import { MessageService } from 'primeng/api';
import type {
  CategoryDistributionItem,
  FinancialSummary,
  MonthlyEvolutionPoint,
  MonthlyPaidPendingPoint,
  PaginatedTransactionsResponse,
  PaymentMethodDistributionItem,
  ReportNarrativeFailedEvent,
  ReportNarrativeReadyEvent,
} from '@amezia/shared-types';
import { filter, map } from 'rxjs';

import { WebSocketService } from '../../../core/websocket/websocket.service';
import { ReportsApiService } from './reports-api.service';
import type { NarrativeState, ReportsDateRange, ReportsFilters } from './reports.models';

const DASHBOARD_RECENT_PAGE_SIZE = 5;
const REPORTS_DEFAULT_PAGE_SIZE = 15;
const DASHBOARD_EVOLUTION_MONTHS = 6;
const NARRATIVE_RETRY_FALLBACK_SECONDS = 10;

interface WsEnvelope {
  event?: string;
}

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function lastDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Mês/ano corrente — período default do Dashboard.
 */
export function currentMonthPeriod(): { year: number; month: number } {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Últimos 6 meses corridos (incl. o atual) — intervalo
 * default da tela de Reports (build-context-05 §3.2).
 */
export function defaultReportsRange(): ReportsDateRange {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() - 5, 1);
  return {
    dateFrom: `${start.getFullYear()}-${pad2(start.getMonth() + 1)}-01`,
    dateTo: `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(lastDayOfMonth(now.getFullYear(), now.getMonth() + 1))}`,
  };
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Estado compartilhado do módulo de Relatórios (Signals) —
 * usado pelas duas telas (Dashboard e Reports, build-context-05 §3.1/
 * §1.2): período/intervalo, filtros, dados agregados, loading por
 * seção e o estado da narrativa IA. `WebSocketService` já está
 * conectado desde o login (build-context-01) — este serviço só assina
 * `messages$` e filtra os eventos de narrativa.
 */
@Injectable({ providedIn: 'root' })
export class ReportsStateService {
  private readonly api = inject(ReportsApiService);
  private readonly webSocketService = inject(WebSocketService);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);

  // Dashboard — período de um mês só
  readonly period = signal(currentMonthPeriod());

  // Reports — intervalo De/Até + filtros + paginação da tabela
  readonly periodRange = signal<ReportsDateRange>(defaultReportsRange());
  readonly filters = signal<ReportsFilters>({ categoryId: '' });
  readonly page = signal(1);
  readonly pageSize = signal(REPORTS_DEFAULT_PAGE_SIZE);

  // Dados agregados (compartilhados pelas duas telas, com parâmetros diferentes)
  readonly summary = signal<FinancialSummary | null>(null);
  readonly monthlyEvolution = signal<MonthlyEvolutionPoint[]>([]);
  readonly categoryDistribution = signal<CategoryDistributionItem[]>([]);
  readonly recentTransactions = signal<PaginatedTransactionsResponse | null>(null);
  readonly transactionsPage = signal<PaginatedTransactionsResponse | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Distribuição por tipo de pagamento e série mensal pago x
   * pendente (últimos 6 meses corridos) — 2 gráficos novos do Dashboard/
   * Reports, pedido direto do usuário, fora de qualquer build-context.
   * Mesmo padrão dos demais agregados: um Signal de dado + um de
   * loading, populados em paralelo com o resto em `loadDashboard()`/
   * `loadReportsSummary()`.
   */
  readonly paymentMethodDistribution = signal<PaymentMethodDistributionItem[]>([]);
  readonly monthlyPaidPending = signal<MonthlyPaidPendingPoint[]>([]);

  // Loading por seção
  readonly summaryLoading = signal(false);
  readonly evolutionLoading = signal(false);
  readonly distributionLoading = signal(false);
  readonly paymentMethodDistributionLoading = signal(false);
  readonly paidPendingLoading = signal(false);
  readonly recentTransactionsLoading = signal(false);
  readonly transactionsLoading = signal(false);
  readonly exportLoading = signal(false);
  readonly dashboardError = signal(false);
  readonly reportsError = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Resultado do último `exportCsv()`, separado de
   * `reportsError` de propósito — antes, qualquer falha na exportação
   * (inclusive limite mensal do plano atingido) caía em `reportsError`,
   * que troca a tela inteira de Relatórios (tabela, gráficos, tudo) por
   * um painel de erro genérico "Não foi possível carregar os
   * relatórios" — enganoso e desproporcional pra uma ação pontual que
   * não tem nada a ver com carregar a página. `'limit_reached'` (403 de
   * `enforce_csv_export_limit`) e `'failed'` (qualquer outro erro) viram
   * um banner discreto perto do botão de exportar, sem afetar o resto
   * da tela.
   */
  readonly exportError = signal<'limit_reached' | 'failed' | null>(null);

  // Narrativa IA
  readonly narrativeState = signal<NarrativeState>('idle');
  readonly narrativeText = signal<string | null>(null);
  readonly narrativeRetryAfterSeconds = signal(NARRATIVE_RETRY_FALLBACK_SECONDS);

  constructor() {
    this.webSocketService.messages$
      .pipe(
        filter((message): message is WsEnvelope => (message as WsEnvelope)?.event === 'report.narrative.ready'),
        map((message) => message as ReportNarrativeReadyEvent),
      )
      .subscribe((event) => this.onNarrativeReady(event));

    this.webSocketService.messages$
      .pipe(
        filter(
          (message): message is WsEnvelope =>
            (message as WsEnvelope)?.event === 'report.narrative.failed',
        ),
        map((message) => message as ReportNarrativeFailedEvent),
      )
      .subscribe((event) => this.onNarrativeFailed(event));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Carrega os 4 blocos do Dashboard em paralelo — resumo,
   * evolução mensal (6 meses corridos até o mês selecionado),
   * distribuição por categoria e as 5 transações mais recentes, todos
   * do mês selecionado (build-context-05 §3.3).
   */
  loadDashboard(year: number, month: number): void {
    this.period.set({ year, month });
    const range = this.monthRange(year, month);

    this.dashboardError.set(false);
    this.summaryLoading.set(true);
    this.api.getSummary(range).subscribe({
      next: (summary) => {
        this.summary.set(summary);
        this.summaryLoading.set(false);
      },
      error: () => {
        this.summaryLoading.set(false);
        this.dashboardError.set(true);
      },
    });

    this.evolutionLoading.set(true);
    this.api.getMonthlyEvolution(year, month, DASHBOARD_EVOLUTION_MONTHS).subscribe({
      next: (points) => {
        this.monthlyEvolution.set(points);
        this.evolutionLoading.set(false);
      },
      error: () => {
        this.evolutionLoading.set(false);
        this.dashboardError.set(true);
      },
    });

    this.distributionLoading.set(true);
    this.api.getCategoryDistribution(range).subscribe({
      next: (items) => {
        this.categoryDistribution.set(items);
        this.distributionLoading.set(false);
      },
      error: () => {
        this.distributionLoading.set(false);
        this.dashboardError.set(true);
      },
    });

    this.recentTransactionsLoading.set(true);
    this.api.getTransactions(range, 1, DASHBOARD_RECENT_PAGE_SIZE).subscribe({
      next: (result) => {
        this.recentTransactions.set(result);
        this.recentTransactionsLoading.set(false);
      },
      error: () => {
        this.recentTransactionsLoading.set(false);
        this.dashboardError.set(true);
      },
    });

    this.paymentMethodDistributionLoading.set(true);
    this.api.getPaymentMethodDistribution(range).subscribe({
      next: (items) => {
        this.paymentMethodDistribution.set(items);
        this.paymentMethodDistributionLoading.set(false);
      },
      error: () => {
        this.paymentMethodDistributionLoading.set(false);
        this.dashboardError.set(true);
      },
    });

    this.paidPendingLoading.set(true);
    this.api.getMonthlyPaidPending(year, month, DASHBOARD_EVOLUTION_MONTHS).subscribe({
      next: (points) => {
        this.monthlyPaidPending.set(points);
        this.paidPendingLoading.set(false);
      },
      error: () => {
        this.paidPendingLoading.set(false);
        this.dashboardError.set(true);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Converte um mês/ano único no intervalo [1º dia, último
   * dia] usado pelas queries de agregação — o Dashboard sempre filtra
   * por um mês, nunca por um `PeriodRange` de verdade. Público (não só
   * uso interno) porque o modal de transações por categoria do
   * Dashboard também precisa montar esse intervalo pra chamar
   * `ReportsApiService.getTransactions` direto (2026-08-18).
   */
  monthRange(year: number, month: number): ReportsDateRange {
    return {
      dateFrom: `${year}-${pad2(month)}-01`,
      dateTo: `${year}-${pad2(month)}-${pad2(lastDayOfMonth(year, month))}`,
    };
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Carrega resumo + ranking de categorias do intervalo/
   * filtros atuais da tela de Reports (build-context-05 §3.4).
   */
  loadReportsSummary(): void {
    const params = this.currentReportsParams();
    this.reportsError.set(false);

    this.summaryLoading.set(true);
    this.api.getSummary(params).subscribe({
      next: (summary) => {
        this.summary.set(summary);
        this.summaryLoading.set(false);
      },
      error: () => {
        this.summaryLoading.set(false);
        this.reportsError.set(true);
      },
    });

    this.distributionLoading.set(true);
    this.api.getCategoryDistribution(params).subscribe({
      next: (items) => {
        this.categoryDistribution.set(items);
        this.distributionLoading.set(false);
      },
      error: () => {
        this.distributionLoading.set(false);
        this.reportsError.set(true);
      },
    });

    this.paymentMethodDistributionLoading.set(true);
    this.api.getPaymentMethodDistribution(params).subscribe({
      next: (items) => {
        this.paymentMethodDistribution.set(items);
        this.paymentMethodDistributionLoading.set(false);
      },
      error: () => {
        this.paymentMethodDistributionLoading.set(false);
        this.reportsError.set(true);
      },
    });

    const { year, month } = this.lastMonthOf(params.dateTo);
    this.paidPendingLoading.set(true);
    this.api.getMonthlyPaidPending(year, month, DASHBOARD_EVOLUTION_MONTHS).subscribe({
      next: (points) => {
        this.monthlyPaidPending.set(points);
        this.paidPendingLoading.set(false);
      },
      error: () => {
        this.paidPendingLoading.set(false);
        this.reportsError.set(true);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Ano/mês do último dia do intervalo De/Até da tela de
   * Reports — referência pro gráfico "Pago x Pendente" (últimos 6 meses
   * corridos até esse mês), já que o intervalo customizado da tela nem
   * sempre cobre exatamente 6 meses.
   */
  private lastMonthOf(dateTo: string): { year: number; month: number } {
    const [year, month] = dateTo.split('-').map(Number);
    return { year, month };
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Carrega a página atual da tabela de transações da tela
   * de Reports.
   */
  loadReportsTransactions(): void {
    const params = this.currentReportsParams();
    this.transactionsLoading.set(true);
    this.api.getTransactions(params, this.page(), this.pageSize()).subscribe({
      next: (result) => {
        this.transactionsPage.set(result);
        this.transactionsLoading.set(false);
      },
      error: () => {
        this.transactionsLoading.set(false);
        this.reportsError.set(true);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Recarrega resumo + ranking + tabela — usado pelo botão
   * "Tentar novamente" e ao entrar na tela.
   */
  loadReports(): void {
    this.loadReportsSummary();
    this.loadReportsTransactions();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Parâmetros de query atuais da tela de Reports (intervalo
   * + filtros), reaproveitados por resumo/ranking/tabela/export.
   */
  private currentReportsParams(): ReportsDateRange & { categoryId?: string } {
    const range = this.periodRange();
    const filters = this.filters();
    return {
      dateFrom: range.dateFrom,
      dateTo: range.dateTo,
      categoryId: filters.categoryId || undefined,
    };
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Aplica intervalo De/Até + filtro de categoria de
   * uma vez (botão "Aplicar" da filter-bar) — volta a paginação para a
   * 1ª página e recarrega tudo numa única passada, em vez de dois
   * métodos separados que disparariam a mesma requisição duas vezes.
   */
  applyPeriodRangeAndFilters(range: ReportsDateRange, filters: ReportsFilters): void {
    this.periodRange.set(range);
    this.filters.set(filters);
    this.page.set(1);
    this.resetNarrative();
    this.loadReports();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Limpa filtros e volta o intervalo ao padrão (últimos 6
   * meses) — botão "Limpar" da filter-bar.
   */
  resetFilters(): void {
    this.applyPeriodRangeAndFilters(defaultReportsRange(), { categoryId: '' });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Navega para outra página da tabela mantendo os demais
   * filtros.
   */
  goToPage(page: number): void {
    this.page.set(page);
    this.loadReportsTransactions();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Baixa o CSV do filtro atual e dispara o download no
   * browser via um link temporário com `URL.createObjectURL` — o nome
   * do arquivo vem do header `Content-Disposition` respondido pelo
   * backend. `403` (`enforce_csv_export_limit`, build-context-09 §2.6)
   * é o único status de erro possível hoje neste endpoint além de rede
   * — vira `exportError = 'limit_reached'` em vez do genérico `'failed'`
   * (2026-09-11, mesmo motivo do `limit_reached` da narrativa IA:
   * repetir a exportação não resolve nada até o próximo ciclo/upgrade).
   * Toast de sucesso (build-context-13) — o erro já tem mensagem própria
   * (`exportError`, banner discreto perto do botão), mas o sucesso
   * ficava mudo, só o download disparando.
   */
  exportCsv(): void {
    this.exportLoading.set(true);
    this.exportError.set(null);
    this.api.exportCsv(this.currentReportsParams()).subscribe({
      next: (response) => {
        this.exportLoading.set(false);
        const blob = response.body;
        if (!blob) {
          return;
        }
        const filename = this.filenameFromContentDisposition(response.headers.get('content-disposition'));
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('toasts.successTitle'),
          detail: this.transloco.translate('toasts.reports.exportSuccess'),
        });
      },
      error: (err: HttpErrorResponse) => {
        this.exportLoading.set(false);
        this.exportError.set(err.status === 403 ? 'limit_reached' : 'failed');
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Fecha o banner de erro da exportação CSV — chamado pelo
   * "x" do banner ou ao disparar uma nova exportação.
   */
  dismissExportError(): void {
    this.exportError.set(null);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Extrai o nome do arquivo do header `Content-Disposition`
   * — cai num nome genérico se o header vier ausente/malformado.
   */
  private filenameFromContentDisposition(header: string | null): string {
    const match = header?.match(/filename="?([^"]+)"?/);
    return match?.[1] ?? 'relatorio.csv';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Dispara `POST /reports/narrative` — o texto chega
   * depois via WebSocket. `429` (throttle) lê `Retry-After` da resposta
   * para reabilitar o botão no tempo certo; outro erro cai no estado
   * "falha do provider" só depois do evento WS, mas erro de rede no
   * próprio POST já é tratado aqui como falha.
   */
  generateNarrative(): void {
    if (this.narrativeState() === 'loading') {
      return;
    }
    this.narrativeState.set('loading');
    const range = this.periodRange();
    const filters = this.filters();
    this.api
      .generateNarrative({
        date_from: range.dateFrom,
        date_to: range.dateTo,
        category_id: filters.categoryId || undefined,
      })
      .subscribe({
        error: (err: HttpErrorResponse) => {
          if (err.status === 429) {
            const retryAfter = Number(err.headers.get('Retry-After'));
            this.narrativeRetryAfterSeconds.set(
              Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : NARRATIVE_RETRY_FALLBACK_SECONDS,
            );
            this.narrativeState.set('throttled');
            return;
          }
          this.narrativeState.set('failed');
        },
      });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Handler do evento WebSocket `report.narrative.ready`.
   */
  private onNarrativeReady(event: ReportNarrativeReadyEvent): void {
    this.narrativeText.set(event.payload.narrative);
    this.narrativeState.set('ready');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Handler do evento WebSocket `report.narrative.failed`.
   * `payload.reason === 'ai_usage_limit_exceeded'` (publicado por
   * `generate_ai_narrative_job` quando `CheckAiUsageLimitUseCase`
   * barra a chamada) vira um estado próprio (`limit_reached`,
   * 2026-09-11) em vez de cair no genérico `failed` — a mensagem de
   * "tente novamente" era enganosa nesse caso: repetir não ajuda até o
   * próximo ciclo ou um upgrade de plano, e o card deve dizer isso.
   */
  private onNarrativeFailed(event: ReportNarrativeFailedEvent): void {
    if (event.payload.reason === 'ai_usage_limit_exceeded') {
      this.narrativeState.set('limit_reached');
      return;
    }
    this.narrativeState.set('failed');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Reseta o card de narrativa ao estado vazio — chamado
   * sempre que o intervalo/filtros mudam, já que uma narrativa antiga
   * não corresponde mais ao período selecionado.
   */
  resetNarrative(): void {
    this.narrativeState.set('idle');
    this.narrativeText.set(null);
  }
}
