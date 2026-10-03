import { Routes } from '@angular/router';

import { adminPublicOnlyGuard } from './core/auth/admin.guard';
import { authGuard, publicOnlyGuard, rootRedirectGuard } from './core/auth/auth.guard';
import { AppShellComponent } from './layout/shell/app-shell.component';
import { SettingsHubComponent } from './layout/shell/settings-hub.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', canActivate: [rootRedirectGuard], children: [] },
  {
    path: 'login',
    canActivate: [publicOnlyGuard],
    loadComponent: () =>
      import('./features/auth/feature/login-page/login-page.component').then(
        (m) => m.LoginPageComponent,
      ),
  },
  {
    // Passo 1/3 do cadastro (build-context-09, 2026-09-10) — escolha de
    // plano antes de criar a conta. Pública, sem sessão nenhuma ainda.
    path: 'register-plan',
    canActivate: [publicOnlyGuard],
    loadComponent: () =>
      import('./features/subscription/feature/register-plan-page/register-plan-page.component').then(
        (m) => m.RegisterPlanPageComponent,
      ),
  },
  {
    path: 'register',
    canActivate: [publicOnlyGuard],
    loadComponent: () =>
      import('./features/auth/feature/register-page/register-page.component').then(
        (m) => m.RegisterPageComponent,
      ),
  },
  {
    path: 'forgot-password',
    canActivate: [publicOnlyGuard],
    loadComponent: () =>
      import(
        './features/auth/feature/forgot-password-page/forgot-password-page.component'
      ).then((m) => m.ForgotPasswordPageComponent),
  },
  {
    path: 'reset-password',
    canActivate: [publicOnlyGuard],
    loadComponent: () =>
      import('./features/auth/feature/reset-password-page/reset-password-page.component').then(
        (m) => m.ResetPasswordPageComponent,
      ),
  },
  {
    path: 'google-callback',
    loadComponent: () =>
      import(
        './features/auth/feature/google-callback-page/google-callback-page.component'
      ).then((m) => m.GoogleCallbackPageComponent),
  },
  {
    // Porta de entrada isolada do Painel Admin — decisão de produto de
    // 2026-08-15: painéis cliente e admin são telas separadas, sem link
    // cruzado entre os dois em nenhuma direção. Nunca aninhada dentro do
    // AppShellComponent (o shell do cliente) nem do bloco `authGuard`
    // abaixo.
    path: 'admin/login',
    canActivate: [adminPublicOnlyGuard],
    loadComponent: () =>
      import('./features/admin/feature/admin-login-page/admin-login-page.component').then(
        (m) => m.AdminLoginPageComponent,
      ),
  },
  {
    path: 'admin',
    loadChildren: () => import('./features/admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  {
    // Link mágico do bot do WhatsApp (modo Relatório, 2026-08-18) — tela
    // pública de propósito (sem `authGuard`/`AppShellComponent`): quem
    // abre não necessariamente tem sessão nenhuma no navegador, só o
    // `?token=` (report_view, TTL curto) mandado pelo bot.
    // `SharedReportPageComponent` aplica o token e renderiza a mesma
    // `ReportsPageComponent` do app, num shell mínimo próprio.
    path: 'reports/shared',
    loadComponent: () =>
      import('./features/reports/feature/shared-report-page/shared-report-page.component').then(
        (m) => m.SharedReportPageComponent,
      ),
  },
  {
    // Confirmação pós-pagamento (build-context-09, 2026-09-10) — pra
    // onde o `success_url` da Checkout Session do Stripe redireciona.
    // Pública/standalone, sem `AppShellComponent`, mesmo espírito de
    // `reports/shared`: quem chega aqui pode não ter sessão restaurada
    // ainda no momento do redirect.
    path: 'checkout-success',
    loadComponent: () =>
      import(
        './features/subscription/feature/checkout-success-page/checkout-success-page.component'
      ).then((m) => m.CheckoutSuccessPageComponent),
  },
  {
    path: '',
    component: AppShellComponent,
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/reports/feature/dashboard-page/dashboard-page.component').then(
            (m) => m.DashboardPageComponent,
          ),
      },
      {
        path: 'reports',
        loadComponent: () =>
          import('./features/reports/feature/reports-page/reports-page.component').then(
            (m) => m.ReportsPageComponent,
          ),
      },
      {
        path: 'agent',
        loadChildren: () =>
          import('./features/agent-chat/agent-chat.routes').then((m) => m.AGENT_CHAT_ROUTES),
      },
      {
        path: 'categories',
        loadChildren: () =>
          import('./features/categories/categories.routes').then((m) => m.CATEGORIES_ROUTES),
      },
      {
        path: 'transactions',
        loadChildren: () =>
          import('./features/transactions/transactions.routes').then(
            (m) => m.TRANSACTIONS_ROUTES,
          ),
      },
      { path: 'settings', component: SettingsHubComponent },
      {
        path: 'settings/profile',
        loadComponent: () =>
          import('./features/auth/feature/profile-page/profile-page.component').then(
            (m) => m.ProfilePageComponent,
          ),
      },
      {
        path: 'settings/feedback',
        loadComponent: () =>
          import('./features/feedback/feature/feedback-page/feedback-page.component').then(
            (m) => m.FeedbackPageComponent,
          ),
      },
      {
        path: 'settings/plans',
        loadComponent: () =>
          import(
            './features/subscription/feature/settings-plans-page/settings-plans-page.component'
          ).then((m) => m.SettingsPlansPageComponent),
      },
      {
        path: 'settings/usage',
        loadComponent: () =>
          import(
            './features/ai-usage/feature/settings-usage-page/settings-usage-page.component'
          ).then((m) => m.SettingsUsagePageComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
