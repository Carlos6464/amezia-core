import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Protege rotas autenticadas — redireciona para /login
 * preservando a URL de destino (returnUrl) quando não há sessão.
 */
export const authGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Complemento do authGuard — se já autenticado, redireciona
 * direto para /dashboard em vez de deixar acessar login/registro/reset.
 */
export const publicOnlyGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return router.createUrlTree(['/dashboard']);
  }

  return true;
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Guard-only route para `/` — redireciona para /dashboard se
 * autenticado, senão /login (build-context-01 §3.3, PRD §5: sem landing
 * page pública). Nunca renderiza componente próprio.
 */
export const rootRedirectGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return router.createUrlTree([authService.isAuthenticated() ? '/dashboard' : '/login']);
};
