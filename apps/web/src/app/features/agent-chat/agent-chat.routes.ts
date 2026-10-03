import { Routes } from '@angular/router';

/**
 * Layout replicado do projeto irmão (2026-08-12): lista de conversas
 * como página própria (`''`) e o chat de cada conversa como outra
 * página (`:publicId`), navegando entre elas — em vez das duas colunas
 * fixas da versão anterior. `new` precisa vir antes de `:publicId` na
 * ordem das rotas: o Angular Router casa segmentos estáticos antes de
 * parametrizados, então uma ordem invertida faria `new` cair sempre no
 * branch `:publicId` (tratado como um `publicId` literal "new").
 */
export const AGENT_CHAT_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./feature/conversation-list-page/conversation-list-page.component').then(
        (m) => m.ConversationListPageComponent,
      ),
  },
  {
    path: 'new',
    loadComponent: () =>
      import('./feature/chat-page/chat-page.component').then((m) => m.ChatPageComponent),
  },
  {
    path: ':publicId',
    loadComponent: () =>
      import('./feature/chat-page/chat-page.component').then((m) => m.ChatPageComponent),
  },
];
