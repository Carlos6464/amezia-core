import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { DialogModule } from 'primeng/dialog';
import { forkJoin, of } from 'rxjs';
import type {
  CategoryDistributionItem,
  DashboardCard,
  PaymentMethodDistributionItem,
  ReportTransaction,
} from '@amezia/shared-types';

import { AuthService } from '../../../../core/auth/auth.service';
import { BrDatePipe } from '../../../../shared/pipes/br-date.pipe';
import { BrlAmountPipe } from '../../../../shared/pipes/brl-amount.pipe';
import {
  formatPhoneDigits,
  isPhoneComplete,
  normalizePhoneForSubmit,
} from '../../../../shared/utils/phone-mask';
import { BudgetService } from '../../../transactions/data-access/budget.service';
import { paymentMethodLabelKey } from '../../../transactions/data-access/payment-method.model';
import { DASHBOARD_CARD_LABEL_KEYS } from '../../data-access/dashboard-layout.model';
import { DashboardLayoutService } from '../../data-access/dashboard-layout.service';
import { ReportsApiService } from '../../data-access/reports-api.service';
import { ReportsStateService } from '../../data-access/reports-state.service';
import { BudgetHeroCardComponent } from '../../ui/budget-hero-card/budget-hero-card.component';
import { CategoryDistributionListComponent } from '../../ui/category-distribution-list/category-distribution-list.component';
import { DonutChartComponent } from '../../ui/donut-chart/donut-chart.component';
import { LineChartComponent } from '../../ui/line-chart/line-chart.component';
import { MetricCardComponent } from '../../ui/metric-card/metric-card.component';
import { PaidPendingBarChartComponent } from '../../ui/paid-pending-bar-chart/paid-pending-bar-chart.component';
import { PaymentMethodDistributionListComponent } from '../../ui/payment-method-distribution-list/payment-method-distribution-list.component';
import { PeriodPickerComponent } from '../../ui/period-picker/period-picker.component';
import { RecentTransactionsListComponent } from '../../ui/recent-transactions-list/recent-transactions-list.component';

const INTL_LOCALE_BY_LANG: Record<string, string> = { 'pt-BR': 'pt-BR', en: 'en-US' };
const CATEGORY_MODAL_PAGE_SIZE = 50;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-14
 * Descrição: Home autenticada (`/dashboard`) — visão rápida do mês
 * selecionado (build-context-05 §3.3): 4 métricas (despesas do
 * período, teto mensal, maior categoria, maior despesa — sem
 * receita/saldo, produto é expense-only), tendência mensal (line-chart,
 * 6 meses), composição por categoria (donut + lista, todas as
 * categorias do período — não só as de maior gasto, ajuste pedido pelo
 * usuário em 2026-08-18) e preview das 5 transações mais recentes.
 * Clicar numa fatia do donut ou numa linha de "Por categoria" abre um
 * modal com o detalhe da categoria (total, percentual, lançamentos do
 * período) — pedido do usuário em 2026-08-18 pra deixar o Dashboard
 * "mais rico"; ver `openCategoryModal`. Reaproveita `ReportsStateService`
 * (compartilhado com a tela de Reports) e `BudgetService` (teto mensal
 * global do usuário, já usado pela listagem de Transações). O card
 * `budget-hero-card` (Planejado vs Realizado) replica o card
 * equivalente do irmão em `/home/adriano/Documentos/projetos/Amezia`
 * — ficou de fora da 1ª versão desta sessão (só os 4 cards pequenos
 * foram trazidos), adicionado a pedido do usuário em 2026-08-15.
 */
@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [
    TranslocoModule,
    RouterLink,
    FormsModule,
    BrlAmountPipe,
    BrDatePipe,
    DialogModule,
    PeriodPickerComponent,
    BudgetHeroCardComponent,
    MetricCardComponent,
    LineChartComponent,
    DonutChartComponent,
    CategoryDistributionListComponent,
    PaymentMethodDistributionListComponent,
    PaidPendingBarChartComponent,
    RecentTransactionsListComponent,
  ],
  templateUrl: './dashboard-page.component.html',
  styleUrl: './dashboard-page.component.css',
})
export class DashboardPageComponent implements OnInit {
  protected readonly state = inject(ReportsStateService);
  protected readonly budgetService = inject(BudgetService);
  protected readonly authService = inject(AuthService);
  protected readonly dashboardLayoutService = inject(DashboardLayoutService);
  private readonly transloco = inject(TranslocoService);
  private readonly reportsApi = inject(ReportsApiService);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Carrega o mês corrente, o teto mensal e o layout
   * personalizado do Dashboard (2026-09-15) ao abrir a tela.
   */
  ngOnInit(): void {
    const { year, month } = this.state.period();
    this.state.loadDashboard(year, month);
    this.budgetService.load();
    this.dashboardLayoutService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Reage à navegação do `period-picker` (setas/atalhos).
   */
  onPeriodChange(period: { year: number; month: number }): void {
    this.state.loadDashboard(period.year, period.month);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Recarrega os 4 blocos do período atual — botão "Tentar
   * novamente" do estado de erro.
   */
  retry(): void {
    const { year, month } = this.state.period();
    this.state.loadDashboard(year, month);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: `true` enquanto qualquer um dos 4 blocos ainda carrega —
   * controla o skeleton da stats-strip.
   */
  protected readonly loadingAny = computed(
    () =>
      this.state.summaryLoading() ||
      this.state.evolutionLoading() ||
      this.state.distributionLoading() ||
      this.state.recentTransactionsLoading(),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Cards visíveis, na ordem personalizada pelo usuário
   * (pedido direto do usuário, fora de qualquer build-context) — o
   * template renderiza um `@for` sobre esta lista em vez dos 3 blocos
   * fixos de antes (`charts-row`/`bottom-row`/`bottom-row-payment`),
   * cada card escolhendo seu próprio conteúdo via `@switch`.
   */
  protected readonly visibleCards = computed<DashboardCard[]>(() =>
    this.dashboardLayoutService
      .layout()
      .filter((preference) => preference.visible)
      .map((preference) => preference.card),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-14
   * Descrição: Percentual do teto mensal já consumido pelas despesas do
   * mês selecionado — `null` se não houver teto definido (card "Teto
   * mensal", mesmo cálculo do irmão em
   * `/home/adriano/Documentos/projetos/Amezia`).
   */
  protected readonly budgetUsagePercent = computed(() => {
    const budget = Number(this.budgetService.monthlyBudget() ?? 0);
    if (!budget) {
      return null;
    }
    const expense = Number(this.state.summary()?.total_expense ?? 0);
    return (expense / budget) * 100;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Rótulo "Agosto de 2026" do mês selecionado, no idioma
   * ativo — usado pelo `budget-hero-card` (mesmo padrão de
   * `PeriodPickerComponent.monthLabel`).
   */
  protected readonly heroPeriodLabel = computed(() => {
    const locale = INTL_LOCALE_BY_LANG[this.transloco.getActiveLang()] ?? 'pt-BR';
    const { year, month } = this.state.period();
    const date = new Date(year, month - 1, 1);
    const formatted = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(date);
    return formatted.charAt(0).toUpperCase() + formatted.slice(1);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Categoria selecionada no donut/lista — `null` fecha o
   * modal (controla `[visible]` do `p-dialog`, mesmo padrão dos demais
   * diálogos inline do projeto, ex.: `TransactionListComponent`).
   */
  protected readonly selectedCategory = signal<CategoryDistributionItem | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Lançamentos da categoria selecionada, no mês do
   * Dashboard — buscados sob demanda ao abrir o modal (não vêm juntos
   * do `categoryDistribution`, que só tem o agregado).
   */
  protected readonly categoryModalTransactions = signal<ReportTransaction[]>([]);
  protected readonly categoryModalLoading = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: `true` quando a categoria tem mais lançamentos do que os
   * `CATEGORY_MODAL_PAGE_SIZE` trazidos — mostra o link "Ver todas em
   * Relatórios" em vez de paginar dentro do modal (o modal é um resumo
   * rápido, não substitui a tela de Relatórios).
   */
  protected readonly categoryModalHasMore = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Abre o modal de detalhe da categoria (clique numa fatia
   * do donut ou numa linha de "Por categoria") e busca os lançamentos
   * dela no mês selecionado via `GET /reports/transactions` — mesmo
   * endpoint que a tabela de Relatórios usa, filtrado por
   * `category_id` + o intervalo do mês corrente do Dashboard.
   */
  protected openCategoryModal(item: CategoryDistributionItem): void {
    this.selectedCategory.set(item);
    this.categoryModalTransactions.set([]);
    this.categoryModalHasMore.set(false);
    this.categoryModalLoading.set(true);

    const { year, month } = this.state.period();
    const range = this.state.monthRange(year, month);
    this.reportsApi.getTransactions({ ...range, categoryId: item.category_id }, 1, CATEGORY_MODAL_PAGE_SIZE).subscribe({
      next: (result) => {
        this.categoryModalTransactions.set(result.items);
        this.categoryModalHasMore.set(result.pagination.total > result.items.length);
        this.categoryModalLoading.set(false);
      },
      error: () => {
        this.categoryModalLoading.set(false);
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Fecha o modal — `(visibleChange)` do `p-dialog` dispara
   * isso tanto no X quanto no clique fora (`dismissableMask`).
   */
  protected closeCategoryModal(): void {
    this.selectedCategory.set(null);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Tipo de pagamento selecionado na lista "Por tipo de
   * pagamento" — mesmo papel de `selectedCategory`, espelhando o
   * clique-pra-modal que a lista de categorias já tinha (pedido direto
   * do usuário, fora de qualquer build-context).
   */
  protected readonly selectedPaymentMethod = signal<PaymentMethodDistributionItem | null>(null);
  protected readonly paymentMethodModalTransactions = signal<ReportTransaction[]>([]);
  protected readonly paymentMethodModalLoading = signal(false);
  protected readonly paymentMethodModalHasMore = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Rótulo traduzido do tipo de pagamento selecionado —
   * `p-dialog [header]` espera uma string pronta, não aceita um pipe
   * `| transloco` direto no binding, então resolve aqui via
   * `TranslocoService.translate()` (mesmo padrão de outros headers de
   * diálogo montados em código neste módulo).
   */
  protected readonly selectedPaymentMethodLabel = computed(() => {
    const item = this.selectedPaymentMethod();
    return item ? this.transloco.translate(paymentMethodLabelKey(item.payment_method)) : '';
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Abre o modal de detalhe do tipo de pagamento (clique
   * numa linha de "Por tipo de pagamento") e busca os lançamentos dele
   * no mês selecionado — mesmo endpoint de `openCategoryModal`, agora
   * filtrado por `paymentMethod` em vez de `categoryId`.
   */
  protected openPaymentMethodModal(item: PaymentMethodDistributionItem): void {
    this.selectedPaymentMethod.set(item);
    this.paymentMethodModalTransactions.set([]);
    this.paymentMethodModalHasMore.set(false);
    this.paymentMethodModalLoading.set(true);

    const { year, month } = this.state.period();
    const range = this.state.monthRange(year, month);
    this.reportsApi
      .getTransactions({ ...range, paymentMethod: item.payment_method }, 1, CATEGORY_MODAL_PAGE_SIZE)
      .subscribe({
        next: (result) => {
          this.paymentMethodModalTransactions.set(result.items);
          this.paymentMethodModalHasMore.set(result.pagination.total > result.items.length);
          this.paymentMethodModalLoading.set(false);
        },
        error: () => {
          this.paymentMethodModalLoading.set(false);
        },
      });
  }

  protected closePaymentMethodModal(): void {
    this.selectedPaymentMethod.set(null);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: `true` quando falta teto mensal OU telefone — controla o
   * banner chamativo de configuração rápida do topo do Dashboard.
   * Pedido do usuário: "OR", não "AND" — cobre também quem já preencheu
   * um dos dois e esqueceu o outro, não só quem nunca configurou nada.
   */
  protected readonly showSetupBanner = computed(
    () => !this.budgetService.monthlyBudget() || !this.authService.currentUser()?.phone,
  );

  protected readonly setupModalVisible = signal(false);
  protected readonly setupBudgetDraft = signal('');
  protected readonly setupPhoneDraft = signal('');
  protected readonly setupSaving = signal(false);
  protected readonly setupSaved = signal(false);
  protected readonly setupError = signal<string | null>(null);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: `true` só quando o rascunho de teto não está vazio e não
   * bate no formato decimal aceito — mesma regra já usada nos outros 2
   * lugares que editam o teto (form de transação, perfil).
   */
  protected readonly setupBudgetInvalid = computed(() => {
    const raw = this.setupBudgetDraft().trim();
    return raw !== '' && !/^\d+([.,]\d{1,2})?$/.test(raw);
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-19
   * Descrição: `true` quando o rascunho de telefone tem dígitos mas não
   * os 13 que a máscara espera (DDI + DDD + assinante) — mesma regra de
   * `ProfilePageComponent` (`phoneCompleteValidator`), aqui como
   * `computed` porque este modal não usa `FormGroup`.
   */
  protected readonly setupPhoneInvalid = computed(
    () => !isPhoneComplete(this.setupPhoneDraft().replace(/\D/g, '')),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Abre o modal de configuração rápida, pré-preenchido com
   * o que já existir (teto/telefone) — o usuário pode ter só um dos
   * dois faltando, e reabrir o modal não deve apagar o que ele já
   * configurou.
   */
  protected openSetupModal(): void {
    this.setupBudgetDraft.set(this.budgetService.monthlyBudget() ?? '');
    this.setupPhoneDraft.set(formatPhoneDigits((this.authService.currentUser()?.phone ?? '').replace(/\D/g, '')));
    this.setupSaved.set(false);
    this.setupError.set(null);
    this.setupModalVisible.set(true);
  }

  protected closeSetupModal(): void {
    this.setupModalVisible.set(false);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Reformata o campo de telefone a cada tecla digitada —
   * mesmo comportamento de `ProfilePageComponent.onPhoneInput`, mesma
   * função utilitária (`formatPhoneDigits`).
   */
  protected onSetupPhoneInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const digits = input.value.replace(/\D/g, '').slice(0, 13);
    const formatted = formatPhoneDigits(digits);
    this.setupPhoneDraft.set(formatted);
    input.value = formatted;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-18
   * Descrição: Salva teto e/ou telefone num único clique — só dispara a
   * chamada de cada campo que de fato mudou (evita, por exemplo,
   * reenviar `phone` sem necessidade e apagar sem querer um valor que
   * o usuário não tocou). `forkJoin` espera as duas em paralelo quando
   * ambas mudam; `of(null)` no lugar de quem não mudou, pra sempre ter
   * as 2 posições do array.
   */
  protected saveSetup(): void {
    if (this.setupBudgetInvalid() || this.setupPhoneInvalid() || this.setupSaving()) {
      return;
    }
    const rawBudget = this.setupBudgetDraft().trim().replace(',', '.');
    const budgetChanged = rawBudget !== (this.budgetService.monthlyBudget() ?? '');

    const normalizedPhone = normalizePhoneForSubmit(this.setupPhoneDraft());
    const phoneChanged = normalizedPhone !== null && normalizedPhone !== (this.authService.currentUser()?.phone ?? '');

    if (!budgetChanged && !phoneChanged) {
      this.setupModalVisible.set(false);
      return;
    }

    this.setupSaving.set(true);
    this.setupError.set(null);

    forkJoin([
      budgetChanged ? this.budgetService.update(rawBudget === '' ? null : rawBudget) : of(null),
      phoneChanged ? this.authService.updateProfile({ phone: normalizedPhone! }) : of(null),
    ]).subscribe({
      next: () => {
        this.setupSaving.set(false);
        this.setupSaved.set(true);
        window.setTimeout(() => this.setupModalVisible.set(false), 900);
      },
      error: () => {
        this.setupSaving.set(false);
        this.setupError.set('transactions.form.errors.generic');
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Rótulos (i18n key) dos 6 cards personalizáveis, exposto
   * pro template do painel de personalização resolver o nome de cada
   * card sem precisar de um `@switch` gigante só pra isso.
   */
  protected readonly cardLabelKeys = DASHBOARD_CARD_LABEL_KEYS;
}
