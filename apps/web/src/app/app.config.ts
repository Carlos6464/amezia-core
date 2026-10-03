import {
  ApplicationConfig,
  inject,
  isDevMode,
  provideAppInitializer,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideServiceWorker } from '@angular/service-worker';
import { providePrimeNG } from 'primeng/config';
import { ConfirmationService, MessageService } from 'primeng/api';
import Aura from '@primeng/themes/aura';
import { provideTransloco } from '@jsverse/transloco';
import { catchError, firstValueFrom, of, switchMap, tap } from 'rxjs';

import { routes } from './app.routes';
import { AuthService } from './core/auth/auth.service';
import { jwtInterceptor } from './core/auth/jwt.interceptor';
import { errorInterceptor } from './core/http/error.interceptor';
import { HttpTranslocoLoader } from './core/i18n/transloco-loader';
import { WebSocketService } from './core/websocket/websocket.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([jwtInterceptor, errorInterceptor])),
    /**
     * Autor: Carlos Adriano
     * Data: 2026-08-08
     * Descrição: O access token vive só em memória (RN-08) — some a cada
     * reload de página. Antes da primeira navegação, tenta restaurar a
     * sessão via /auth/refresh (cookie httpOnly) para o authGuard não
     * deslogar o usuário a cada F5 mesmo com um refresh token válido.
     * Falha silenciosamente (usuário simplesmente não está autenticado).
     * Reconecta o WebSocket com o token restaurado (bug real encontrado
     * no build-context-04: antes só `_applySession`/`completeGoogleRedirect`
     * chamavam `connect()` — um F5 deixava o usuário autenticado mas sem
     * WebSocket, e isso nunca tinha sido notado porque nenhuma feature
     * dependia de verdade do WebSocket antes do Agente de IA).
     */
    provideAppInitializer(() => {
      const authService = inject(AuthService);
      const webSocketService = inject(WebSocketService);
      return firstValueFrom(
        authService.refreshAccessToken().pipe(
          switchMap((accessToken) =>
            authService.loadCurrentUser().pipe(tap(() => webSocketService.connect(accessToken))),
          ),
          catchError(() => of(null)),
        ),
      );
    }),
    provideAnimationsAsync(),
    /**
     * Autor: Carlos Adriano
     * Data: 2026-08-09
     * Descrição: `darkModeSelector` do PrimeNG é `"system"` por padrão
     * (segue `prefers-color-scheme` do SO) — desconectado do toggle de
     * tema do app (`ThemeService`, que alterna `data-theme` na raiz do
     * documento). Sem isso, componentes PrimeNG (Dialog, ConfirmDialog,
     * Button...) ignoravam o dark mode escolhido pelo usuário e ficavam
     * sempre claros. Aponta pro mesmo atributo que `styles.css` já usa
     * (`:root[data-theme="dark"]`).
     */
    providePrimeNG({
      theme: { preset: Aura, options: { darkModeSelector: '[data-theme="dark"]' } },
    }),
    ConfirmationService,
    /**
     * Autor: Carlos Adriano
     * Data: 2026-08-18
     * Descrição: Provider global do `MessageService` (PrimeNG) — habilita
     * toasts em qualquer componente da árvore (injeção direta, mesmo
     * padrão já usado por `ConfirmationService`). Um único `<p-toast />`
     * fica montado na raiz (`AppComponent`), cobrindo cliente/admin/telas
     * públicas sem precisar de outlet duplicado por shell. Primeiro uso:
     * erro de servidor no formulário de Transações (antes só um banner
     * inline no topo do form).
     */
    MessageService,
    provideTransloco({
      config: {
        availableLangs: ['pt-BR', 'en'],
        defaultLang: 'pt-BR',
        fallbackLang: 'pt-BR',
        reRenderOnLangChange: true,
        prodMode: false,
      },
      loader: HttpTranslocoLoader,
    }),
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000',
    }),
  ],
};
