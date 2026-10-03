import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Protege as rotas internas do Painel Admin (`/admin/overview`,
 * `/admin/users`, `/admin/whatsapp`, `/admin/feedback`) — exige sessão
 * válida **e** `role === 'admin'`, redirecionando pra `/admin/login`
 * (nunca `/login`) em qualquer um dos dois casos. Diferente do desenho
 * original do build-context-06 (`[authGuard, adminGuard]`, dois guards
 * encadeados), este guard sozinho cobre autenticação + papel — decisão
 * de produto de 2026-08-15: os painéis cliente e admin são isolados, e
 * `authGuard` sempre redireciona pra `/login` (a porta do cliente), o
 * que vazaria a isolação. A checagem real de autorização (a que
 * importa) sempre foi o backend (`get_current_admin_user`, 403 se não
 * for admin) — este guard só evita a navegação/flash de UI.
 */
export const adminGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const user = authService.currentUser();
  if (!authService.isAuthenticated() || user?.role !== 'admin') {
    return router.createUrlTree(['/admin/login']);
  }

  return true;
};

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Complemento do adminGuard, mesmo espírito do publicOnlyGuard
 * — se a aba já tem sessão válida com `role='admin'`, pula direto pro
 * `/admin/overview` em vez de mostrar o formulário de `/admin/login` de
 * novo. Uma sessão de `role='user'` (cliente comum) não é redirecionada
 * daqui — continua vendo o formulário normalmente, sem revelar que já
 * está autenticada como cliente.
 */
export const adminPublicOnlyGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated() && authService.currentUser()?.role === 'admin') {
    return router.createUrlTree(['/admin/overview']);
  }

  return true;
};
