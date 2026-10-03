import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './auth.service';
import { SKIP_AUTH_INTERCEPTOR } from '../http/skip-auth-interceptor.token';

const REFRESH_URL = '/api/v1/auth/refresh';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Injeta Authorization: Bearer <access_token> em toda chamada a
 * /api/*; em resposta 401, tenta renovar via /auth/refresh uma única vez
 * (cookie httpOnly enviado automaticamente pelo browser) e repete a
 * requisição original. Se o refresh também falhar, limpa a sessão e
 * redireciona para /login. Só tenta essa dança de refresh quando a
 * requisição original **tinha** um token anexado (`shouldAuthorize`) —
 * um 401 numa chamada sem token (ex.: `/auth/login`, `/admin/auth/login`
 * com credenciais erradas) não é "sessão expirou", é só "essa chamada
 * falhou", e quem chamou (o próprio formulário) já trata isso. Bug real
 * encontrado em 2026-08-15 (build-context-06): sem essa checagem, um
 * 401 do login do admin acionava esse fallback e redirecionava pra
 * `/login` (a porta do cliente) — furando o isolamento entre os dois
 * painéis. Passava despercebido em `/login` porque lá o redirect era um
 * no-op (já estava na mesma rota). Requisições marcadas com
 * `SKIP_AUTH_INTERCEPTOR` (2026-08-18, ex.: `SharedReportPageComponent`
 * — o link mágico do bot do WhatsApp) nem entram nessa lógica: elas têm
 * seu próprio token, sem ligação nenhuma com `AuthService`/sessão do
 * app, e montam o header `Authorization` na mão.
 */
export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.context.get(SKIP_AUTH_INTERCEPTOR)) {
    return next(req);
  }

  const authService = inject(AuthService);
  const router = inject(Router);

  const isApiRequest = req.url.startsWith('/api/');
  const isRefreshRequest = req.url === REFRESH_URL;

  const token = authService.accessToken();
  const shouldAuthorize = isApiRequest && !!token && !isRefreshRequest;
  const authorizedReq = shouldAuthorize
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authorizedReq).pipe(
    catchError((error: unknown) => {
      if (
        !(error instanceof HttpErrorResponse) ||
        error.status !== 401 ||
        !isApiRequest ||
        isRefreshRequest ||
        !shouldAuthorize
      ) {
        return throwError(() => error);
      }

      return authService.refreshAccessToken().pipe(
        switchMap((newToken) =>
          next(req.clone({ setHeaders: { Authorization: `Bearer ${newToken}` } })),
        ),
        catchError((refreshError: unknown) => {
          authService.clearSession();
          router.navigate(['/login']);
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
