import { HttpContextToken } from '@angular/common/http';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-18
 * Descrição: Marca uma requisição pra `jwtInterceptor` ignorar
 * completamente — nem lê `AuthService.accessToken()`, nem tenta
 * renovar/redirecionar num 401. Existe pra telas genuinamente fora do
 * sistema autenticado (ex.: `SharedReportPageComponent`, o link mágico
 * do bot do WhatsApp) que têm seu próprio token (não ligado a
 * `AuthService`) e montam o header `Authorization` na mão — sem isso,
 * o interceptor sobrescreveria esse header com o que estiver em
 * `AuthService.accessToken()` (`null` pro visitante comum, ou o token
 * de uma sessão real se o mesmo navegador por acaso já estiver logado
 * no app), quebrando a independência dessas telas.
 */
export const SKIP_AUTH_INTERCEPTOR = new HttpContextToken<boolean>(() => false);
