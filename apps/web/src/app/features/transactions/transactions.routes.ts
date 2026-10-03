import { Routes } from '@angular/router';

export const TRANSACTIONS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./feature/transaction-list/transaction-list.component').then(
        (m) => m.TransactionListComponent,
      ),
  },
  {
    path: 'new',
    loadComponent: () =>
      import('./feature/transaction-form/transaction-form.component').then(
        (m) => m.TransactionFormComponent,
      ),
  },
  {
    path: ':publicId/edit',
    loadComponent: () =>
      import('./feature/transaction-form/transaction-form.component').then(
        (m) => m.TransactionFormComponent,
      ),
  },
];
