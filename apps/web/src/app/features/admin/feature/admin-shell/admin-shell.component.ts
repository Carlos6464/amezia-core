import { Component, ElementRef, HostListener, OnDestroy, OnInit, ViewChild, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import { filter, map } from 'rxjs';

import { AuthService } from '../../../../core/auth/auth.service';
import { ThemeService } from '../../../../core/theme/theme.service';
import { BreakpointService } from '../../../../core/viewport/breakpoint.service';

const SIDEBAR_COLLAPSED_KEY = 'amezia-admin-sidebar-collapsed';

/**
 * Rotas que aparecem como abas da barra inferior no mobile do Admin — as
 * mesmas 4 do `AppShellComponent` do cliente, mesmo espírito: qualquer
 * outra rota (Feedback, Planos, Uso de IA, Pagamentos, Perfil) some da
 * barra e mostra uma seta de voltar no lugar, alcançável só pelo hub de
 * Configurações (2026-09-11, pedido do usuário — Feedback/Planos
 * estavam soltos na barra em vez de dentro de Configurações).
 */
const ADMIN_MOBILE_TAB_ROUTES = ['/admin/overview', '/admin/users', '/admin/whatsapp', '/admin/settings'];

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-11
 * Descrição: Alvo da seta de voltar no mobile do Admin — alvo fixo por
 * rota (não histórico do navegador), mesmo princípio do
 * `mobileBackTarget` do painel cliente. Diferente do cliente, o Admin
 * não tem múltiplos pontos de entrada pra uma mesma sub-rota — quase
 * tudo é alcançado a partir do hub de Configurações, exceto o
 * formulário de preço (`/admin/plans/new`), que volta pra listagem.
 */
function adminMobileBackTarget(path: string): string {
  if (path === '/admin/plans/new') {
    return '/admin/plans';
  }
  return '/admin/settings';
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Gera as iniciais do avatar da topbar (primeiro + último
 * nome) — mesma função de `AppShellComponent`, duplicada aqui porque o
 * Painel Admin não importa nada do painel cliente (painéis isolados).
 */
function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Shell do Painel Admin (topbar + sidebar colapsável +
 * `<router-outlet>` + barra de abas no mobile) — mesmo padrão de
 * navegação do `AppShellComponent` (painel cliente), duplicado aqui de
 * propósito (não importado de lá, painéis isolados por decisão de
 * produto de 2026-08-15) com as 4 rotas do Admin e a paleta preta em
 * vez das do cliente. Liga `data-panel="admin"` na raiz do documento ao
 * entrar, remove ao sair — é o que troca a paleta de destaque
 * (`styles.css`), sem afetar o toggle claro/escuro (`data-theme`,
 * ortogonal a este).
 */
@Component({
  selector: 'app-admin-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, TranslocoModule],
  templateUrl: './admin-shell.component.html',
  styleUrl: './admin-shell.component.css',
})
export class AdminShellComponent implements OnInit, OnDestroy {
  protected readonly authService = inject(AuthService);
  protected readonly themeService = inject(ThemeService);
  protected readonly breakpoint = inject(BreakpointService);
  private readonly router = inject(Router);

  @ViewChild('userMenuWrap') private readonly userMenuWrapRef?: ElementRef<HTMLElement>;

  protected readonly initials = computed(() => initialsOf(this.authService.currentUser()?.name ?? ''));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: URL ativa como Signal (via eventos de navegação) — usada
   * pra decidir se a rota atual é uma das abas principais do mobile ou
   * uma sub-página (mostra seta de voltar em vez da barra de abas).
   * Mesmo padrão de `AppShellComponent`.
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
   * Data: 2026-09-11
   * Descrição: `true` quando a rota atual é uma das 4 abas principais
   * do mobile — controla a barra de abas inferior vs. a seta de voltar.
   */
  private readonly isTabRoute = computed(() => ADMIN_MOBILE_TAB_ROUTES.includes(this.currentUrl()));

  protected readonly showBottomNav = computed(() => this.breakpoint.isMobile() && this.isTabRoute());

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-11
   * Descrição: Seta de voltar global do topbar do Admin, mesmo padrão
   * do painel cliente — substitui o hambúrguer/marca e esconde o
   * avatar enquanto ativa.
   */
  protected readonly showBackHeader = computed(
    () => this.breakpoint.isMobile() && !this.isTabRoute(),
  );
  protected readonly backTarget = computed(() => adminMobileBackTarget(this.currentUrl()));

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Colapso manual da sidebar (ícones-só vs. completa),
   * persistido em `localStorage` sob chave própria do admin — mesmo
   * padrão de `AppShellComponent`, storage separado pra não colidir
   * com a preferência do painel cliente.
   */
  protected readonly sidebarCollapsed = signal(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true');

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: `true` quando o dropdown do avatar está aberto.
   */
  readonly userMenuOpen = signal(false);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Ativa o tema preto do painel admin ao montar o shell.
   */
  ngOnInit(): void {
    document.documentElement.dataset['panel'] = 'admin';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Remove o tema preto ao sair do painel admin — sem isso,
   * navegar de volta pro painel cliente manteria a paleta preta
   * indevidamente.
   */
  ngOnDestroy(): void {
    delete document.documentElement.dataset['panel'];
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Alterna e persiste o colapso da sidebar — chamado pelo
   * botão hambúrguer no topo dela.
   */
  toggleSidebar(): void {
    this.sidebarCollapsed.update((collapsed) => !collapsed);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(this.sidebarCollapsed()));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Abre/fecha o dropdown do avatar.
   */
  toggleUserMenu(): void {
    this.userMenuOpen.update((open) => !open);
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Encerra a sessão e volta pra `/admin/login` — nunca pra
   * `/login` (a porta do cliente), painéis isolados.
   */
  logout(): void {
    this.userMenuOpen.set(false);
    this.authService.logout('/admin/login');
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Fecha o dropdown do avatar ao clicar fora dele —
   * escopado ao `#userMenuWrap`, mesmo padrão de `AppShellComponent`.
   */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.userMenuOpen() && !this.userMenuWrapRef?.nativeElement.contains(event.target as Node)) {
      this.userMenuOpen.set(false);
    }
  }
}
