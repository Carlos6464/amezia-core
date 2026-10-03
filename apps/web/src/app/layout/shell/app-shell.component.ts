import {
  Component,
  ElementRef,
  HostListener,
  OnInit,
  ViewChild,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import { filter, map } from 'rxjs';

import type { Plan } from '@amezia/shared-types';

import { AuthService } from '../../core/auth/auth.service';
import { ThemeService } from '../../core/theme/theme.service';
import { BreakpointService } from '../../core/viewport/breakpoint.service';
import { DashboardLayoutService } from '../../features/reports/data-access/dashboard-layout.service';
import { SubscriptionService } from '../../features/subscription/data-access/subscription.service';
import { OnboardingChecklistComponent } from '../onboarding/onboarding-checklist.component';
import { OnboardingTourComponent } from '../onboarding/onboarding-tour.component';
import { OnboardingService } from '../onboarding/onboarding.service';

const SIDEBAR_COLLAPSED_KEY = 'amezia-sidebar-collapsed';

/**
 * Rotas de nível raiz que aparecem como abas da barra inferior no mobile
 * (visão de app, ver ajuste de 2026-08-09). Qualquer outra rota some da
 * barra e mostra uma seta de voltar no lugar. "Relatórios" entrou como
 * 5ª aba em 2026-08-15 (pedido do usuário) — antes só existia dentro do
 * hub de Configurações, já que a barra era deliberadamente fixa em 4
 * itens (ver `DIARIO.md`, build-context-05); essa restrição foi
 * revisada a pedido explícito do usuário.
 */
const MOBILE_TAB_ROUTES = ['/dashboard', '/reports', '/transactions', '/agent', '/settings'];

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-12
 * Descrição: `/agent/new` e `/agent/:publicId` (chat de uma conversa,
 * layout replicado do projeto irmão) já têm sua própria seta de voltar
 * integrada ao cabeçalho da página (ícone + título da conversa, ao
 * lado dela) — mostrar também a seta de voltar global do topbar
 * duplicaria o controle (bug real encontrado na validação em mobile,
 * 2026-08-12). `showBackHeader` usa esta função pra suprimir a seta
 * global só nessas sub-rotas.
 */
function isAgentConversationRoute(path: string): boolean {
  return path.startsWith('/agent/');
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Gera as iniciais do avatar da topbar (primeiro + último
 * nome) a partir do nome completo.
 */
function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-10
 * Descrição: Alvo da seta de voltar no mobile para uma rota "de dentro"
 * (fora das 4 abas principais). Continua sendo um alvo fixo por rota, não
 * histórico do navegador (previsível mesmo em deep link direto) — com uma
 * exceção deliberada: `/transactions/new` pode ser aberta tanto do
 * Dashboard (FAB) quanto da listagem (FAB mobile ou CTAs), então o próprio
 * link de origem carrega `?from=dashboard|transactions` na navegação, e
 * aqui só lemos essa informação em vez de assumir um alvo único. Sem
 * `from` (ex.: `/transactions/:publicId/edit`, sempre aberta a partir da
 * listagem), cai no mesmo alvo fixo de sempre.
 */
function mobileBackTarget(url: string): string {
  const [path, query] = url.split('?');
  const from = new URLSearchParams(query ?? '').get('from');
  if (from === 'dashboard') {
    return '/dashboard';
  }
  if (from === 'transactions') {
    return '/transactions';
  }
  if (path === '/categories' || path.startsWith('/settings/')) {
    return '/settings';
  }
  if (path.startsWith('/transactions/')) {
    return '/transactions';
  }
  if (path.startsWith('/agent/')) {
    return '/agent';
  }
  return '/dashboard';
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Shell autenticado (topbar + sidebar + router-outlet),
 * reaproveitado por todas as páginas protegidas pelo authGuard — evolução
 * da casca vazia do build-context-00 (§3.1: "sem navegação de features
 * ainda"). Itens de sidebar de módulos não implementados (Planos,
 * Suporte, Feedback...) não são renderizados (build-context-01 §3.2.4).
 * Desde 2026-08-09, a navegação se comporta de dois jeitos diferentes por
 * viewport: desktop mantém a sidebar (agora fixa na tela, com colapso
 * manual via hambúrguer); mobile troca a sidebar por uma barra de abas
 * inferior no estilo app nativo/PWA, com seta de voltar nas rotas que não
 * são uma das 4 abas principais.
 */
@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    TranslocoModule,
    OnboardingTourComponent,
    OnboardingChecklistComponent,
  ],
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.css',
})
export class AppShellComponent implements OnInit {
  protected readonly authService = inject(AuthService);
  protected readonly themeService = inject(ThemeService);
  protected readonly breakpoint = inject(BreakpointService);
  protected readonly onboarding = inject(OnboardingService);
  protected readonly dashboardLayoutService = inject(DashboardLayoutService);
  private readonly subscriptionService = inject(SubscriptionService);
  private readonly router = inject(Router);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Dispara o onboarding guiado (tour + checklist) no
   * primeiro load do shell autenticado — só mostra algo se o backend
   * ainda não marca `onboarding_completed` (`OnboardingService.
   * initForUser`).
   */
  ngOnInit(): void {
    this.onboarding.initForUser();
    this.subscriptionService.loadMySubscription();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Plano efetivo do usuário logado (considera o cohort
   * legado via `resolve_effective_plan()` no backend) — `'free'` até a
   * resposta de `GET /subscriptions/me` chegar, pra badge/CTA do
   * header nunca ficarem num estado indefinido. Pedido do usuário: o
   * plano estava "escondido" dentro do Perfil, precisava aparecer em
   * algum lugar sempre visível.
   */
  protected readonly currentPlan = computed<Plan>(
    () => this.subscriptionService.mySubscription()?.effective_plan ?? 'free',
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: `true` quando o Admin concedeu acesso de teste Premium
   * vitalício (sem Stripe) a esta conta — controla a visibilidade de
   * toda a área de plano/cobrança em qualquer lugar do shell: quem tem
   * esse acesso não tem assinatura real por trás, então não faz
   * sentido deixar a pessoa ver/mexer em checkout, portal de cobrança
   * ou upgrade (pedido direto do usuário, fora de qualquer
   * build-context).
   */
  protected readonly isAdminTestAccess = computed(
    () => this.subscriptionService.mySubscription()?.is_admin_test_access ?? false,
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: `true` também para quem tem papel `admin` (não só
   * acesso de teste) — pedido do usuário: um admin navegando no app do
   * cliente comum (fora do painel `/admin`) não pode ver a área de
   * plano/cobrança, mesmo motivo de `isAdminTestAccess` (a conta do
   * admin não é o alvo de upgrade/checkout do produto). É esta flag,
   * não `isAdminTestAccess` sozinha, que controla o que o template
   * esconde.
   */
  protected readonly hidePlanArea = computed(
    () => this.isAdminTestAccess() || this.authService.currentUser()?.role === 'admin',
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: `true` enquanto o plano efetivo não for o topo (Premium)
   * — controla o botão de upgrade no header, que não faz sentido exibir
   * pra quem já está no plano mais alto. Nunca `true` em acesso de
   * teste do admin nem pra papel `admin` (2026-09-15) — ver
   * `hidePlanArea`.
   */
  protected readonly showUpgradeCta = computed(
    () => this.currentPlan() !== 'premium' && !this.hidePlanArea(),
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-16
   * Descrição: Marca o item "Conversar com o Agente" do checklist só
   * por navegar até `/agent` (mesmo critério do projeto irmão — não
   * exige enviar mensagem, só visitar a tela já conta).
   */
  private readonly markAgentVisited = effect(() => {
    if (this.currentUrl().startsWith('/agent')) {
      this.onboarding.markDone('agent');
    }
  });

  @ViewChild('userMenuWrap') private readonly userMenuWrapRef?: ElementRef<HTMLElement>;

  protected readonly initials = computed(() => initialsOf(this.authService.currentUser()?.name ?? ''));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: URL ativa como Signal (via eventos de navegação) — usada
   * para decidir visibilidade do FAB, da barra de abas mobile e da seta
   * de voltar.
   */
  private readonly currentUrl = toSignal(
    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd),
      map((event) => event.urlAfterRedirects),
    ),
    { initialValue: this.router.url },
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Colapso manual da sidebar no desktop (ícones-só vs.
   * completa), acionado pelo botão hambúrguer — persistido em
   * `localStorage` porque é preferência do usuário, não estado da sessão
   * (mesmo padrão já usado por `ThemeService`).
   */
  protected readonly sidebarCollapsed = signal(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true');

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Alterna e persiste o colapso da sidebar — chamado pelo
   * botão hambúrguer no topo dela.
   */
  toggleSidebar(): void {
    this.sidebarCollapsed.update((collapsed) => !collapsed);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(this.sidebarCollapsed()));
    this.dispatchResizeAfterSidebarTransition();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Dispara um evento `resize` global depois que a transição
   * CSS de largura da sidebar termina (`.sidebar { transition: width
   * 0.15s }`) — bug real reportado pelo usuário: gráficos Chart.js
   * (`p-chart`, módulo Relatórios) ficavam com largura errada ao
   * colapsar/expandir a sidebar. O `ResizeObserver` interno do Chart.js
   * observa o container do canvas, então em teoria já reagiria sozinho
   * a qualquer mudança de caixa — mas colapsar a sidebar não dispara
   * nenhum evento `resize` do `window`, e o redimensionamento contínuo
   * durante uma transição CSS (múltiplos disparos por frame, com
   * throttle interno do Chart.js) pode convergir pra uma medida
   * intermediária em vez da largura final. Disparar `resize` manualmente
   * após o fim da transição força todo `p-chart` da tela a reconferir o
   * tamanho certo — mesmo truque padrão usado em qualquer app com
   * sidebar colapsável + Chart.js.
   */
  private dispatchResizeAfterSidebarTransition(): void {
    setTimeout(() => window.dispatchEvent(new Event('resize')), 200);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: `true` quando a rota atual é uma das 4 abas principais do
   * mobile — controla a barra de abas inferior vs. a seta de voltar.
   */
  private readonly isTabRoute = computed(() => MOBILE_TAB_ROUTES.includes(this.currentUrl()));

  protected readonly showBottomNav = computed(() => this.breakpoint.isMobile() && this.isTabRoute());

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: `true` só na rota `/dashboard` — controla o botão
   * "Personalizar" do topbar global (pedido direto do usuário: o botão
   * precisava ficar no cabeçalho de verdade do app, junto do botão de
   * tema claro/escuro, não dentro do cabeçalho local da página do
   * Dashboard). A personalização só faz sentido nessa tela, então o
   * botão não aparece nas demais.
   */
  protected readonly isDashboardRoute = computed(() => this.currentUrl() === '/dashboard');

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Seta de voltar global do topbar — escondida em
   * `/agent/new`/`/agent/:publicId` porque a própria página do chat já
   * tem sua seta de voltar integrada ao cabeçalho (ícone + título ao
   * lado, layout replicado do projeto irmão); mostrar as duas juntas
   * duplicava o controle (bug real encontrado na validação em mobile).
   */
  protected readonly showBackHeader = computed(
    () =>
      this.breakpoint.isMobile() &&
      !this.isTabRoute() &&
      !isAgentConversationRoute(this.currentUrl()),
  );
  protected readonly backTarget = computed(() => mobileBackTarget(this.currentUrl()));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-09
   * Descrição: Visibilidade do FAB de registro rápido — só existe em 2
   * telas (pedido explícito do usuário): o Dashboard (`/dashboard`,
   * sempre, desktop e mobile) e a listagem de Transações (`/transactions`
   * exato). Na listagem, o desktop já tem o CTA "Nova transação" no
   * cabeçalho — FAB fica redundante lá; no mobile esse CTA é escondido
   * por espaço (`transaction-design.css`), então o FAB precisa ser o
   * único ponto de entrada. Em qualquer outra rota (Categorias,
   * Configurações, Agente, formulários de transação) o FAB não aparece.
   */
  protected readonly showQuickAddFab = computed(() => {
    const url = this.currentUrl();
    if (url === '/dashboard') {
      return true;
    }
    if (url === '/transactions') {
      return this.breakpoint.isMobile();
    }
    return false;
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Origem do FAB (Dashboard ou listagem de Transações) —
   * enviada como `?from=` na navegação pra `/transactions/new`, pra a
   * seta de voltar mobile saber devolver o usuário pro mesmo lugar de
   * onde ele veio (ver `mobileBackTarget`).
   */
  protected readonly quickAddOrigin = computed<'dashboard' | 'transactions'>(() =>
    this.currentUrl() === '/transactions' ? 'transactions' : 'dashboard',
  );

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Aciona o logout (limpa sessão + navega para /login) a
   * partir do menu do avatar (desktop) ou do hub de Configurações
   * (mobile).
   */
  logout(): void {
    this.userMenuOpen.set(false);
    this.authService.logout();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: `true` quando o dropdown do avatar (desktop — Perfil +
   * Sair, ver ajuste de 2026-08-10) está aberto. No mobile o avatar
   * continua um link direto pro Perfil (Sair já é alcançável pelo hub
   * de Configurações), então esse Signal só é lido no ramo desktop do
   * template.
   */
  readonly userMenuOpen = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Abre/fecha o dropdown do avatar.
   */
  toggleUserMenu(): void {
    this.userMenuOpen.update((open) => !open);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-10
   * Descrição: Fecha o dropdown do avatar ao clicar fora dele — mesmo
   * padrão de `CategorySelectComponent`/`PaymentMethodSelectComponent`,
   * mas escopado ao `#userMenuWrap` (não ao host inteiro do shell, que
   * envolve a aplicação inteira e tornaria a checagem inútil).
   */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.userMenuOpen() && !this.userMenuWrapRef?.nativeElement.contains(event.target as Node)) {
      this.userMenuOpen.set(false);
    }
  }
}
