import { Routes } from '@angular/router';

import { adminGuard } from '../../core/auth/admin.guard';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Rotas internas do Painel Admin (build-context-06 §3.2) —
 * carregadas via `loadChildren` a partir de `app.routes.ts`, mantendo o
 * bundle inicial do cliente leve (usuário comum nunca baixa este
 * módulo). `adminGuard` protege o shell inteiro (autenticação + papel),
 * uma vez só, cobrindo as 4 telas filhas.
 */
export const ADMIN_ROUTES: Routes = [
  {
    path: '',
    canActivate: [adminGuard],
    loadComponent: () =>
      import('./feature/admin-shell/admin-shell.component').then((m) => m.AdminShellComponent),
    children: [
      { path: '', redirectTo: 'overview', pathMatch: 'full' },
      {
        path: 'overview',
        loadComponent: () =>
          import('./feature/admin-overview-page/admin-overview-page.component').then(
            (m) => m.AdminOverviewPageComponent,
          ),
      },
      {
        path: 'users',
        loadComponent: () =>
          import('./feature/admin-users-page/admin-users-page.component').then(
            (m) => m.AdminUsersPageComponent,
          ),
      },
      {
        path: 'whatsapp',
        loadComponent: () =>
          import('./feature/admin-whatsapp-page/admin-whatsapp-page.component').then(
            (m) => m.AdminWhatsappPageComponent,
          ),
      },
      {
        path: 'feedback',
        loadComponent: () =>
          import('./feature/admin-feedback-page/admin-feedback-page.component').then(
            (m) => m.AdminFeedbackPageComponent,
          ),
      },
      {
        path: 'plans',
        loadComponent: () =>
          import('./feature/admin-plans-page/admin-plans-page.component').then(
            (m) => m.AdminPlansPageComponent,
          ),
      },
      {
        path: 'plans/new',
        loadComponent: () =>
          import('./feature/admin-plan-price-form-page/admin-plan-price-form-page.component').then(
            (m) => m.AdminPlanPriceFormPageComponent,
          ),
      },
      {
        path: 'ai-usage',
        loadComponent: () =>
          import('./feature/admin-ai-usage-page/admin-ai-usage-page.component').then(
            (m) => m.AdminAiUsagePageComponent,
          ),
      },
      {
        path: 'payments',
        loadComponent: () =>
          import('./feature/admin-payments-page/admin-payments-page.component').then(
            (m) => m.AdminPaymentsPageComponent,
          ),
      },
      {
        path: 'profile',
        loadComponent: () =>
          import('./feature/admin-profile-page/admin-profile-page.component').then(
            (m) => m.AdminProfilePageComponent,
          ),
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./feature/admin-settings-hub/admin-settings-hub.component').then(
            (m) => m.AdminSettingsHubComponent,
          ),
      },
    ],
  },
];
