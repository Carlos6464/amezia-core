import { DestroyRef, Injectable, inject, signal } from '@angular/core';

/**
 * Mesma largura usada em todo o design system para o breakpoint
 * mobile/desktop (`transaction-design.css`, `category-design.css`,
 * `app-shell.component.css`) — centralizada aqui só para o lado JS da
 * detecção; o valor em si ainda precisa ser repetido em cada `@media`
 * de CSS, já que CSS não lê constantes do TypeScript.
 */
const MOBILE_BREAKPOINT_QUERY = '(max-width: 700px)';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-09
 * Descrição: Signal reativo ao breakpoint mobile (`matchMedia`) —
 * extraído de `AppShellComponent` para um serviço singleton porque mais
 * de um componente (shell, e agora o filtro de transações) precisa saber
 * se a navegação/layout deve se comportar como mobile, não só via CSS
 * (mudança de comportamento, não só de tamanho).
 */
@Injectable({ providedIn: 'root' })
export class BreakpointService {
  private readonly destroyRef = inject(DestroyRef);

  readonly isMobile = signal(window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches);

  constructor() {
    const mediaQuery = window.matchMedia(MOBILE_BREAKPOINT_QUERY);
    const listener = (event: MediaQueryListEvent) => this.isMobile.set(event.matches);
    mediaQuery.addEventListener('change', listener);
    this.destroyRef.onDestroy(() => mediaQuery.removeEventListener('change', listener));
  }
}
