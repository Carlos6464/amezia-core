import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-06
 * Descrição: Loga erros de requisições HTTP e repassa o erro adiante.
 * O authInterceptor (refresh silencioso em 401) chega no build-context-01.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    catchError((error) => {
      console.error(`[HTTP] ${req.method} ${req.url} failed`, error);
      return throwError(() => error);
    }),
  );
};
