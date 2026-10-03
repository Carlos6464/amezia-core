import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';

import { AuthService } from '../../../../core/auth/auth.service';
import { AdminBrandPanelComponent } from '../../ui/admin-brand-panel/admin-brand-panel.component';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Tela `/admin/login` — porta de entrada isolada do Painel
 * Admin (decisão de produto de 2026-08-15: painéis cliente/admin
 * separados, sem link cruzado entre os dois). Sem "criar conta" (admin
 * não se auto-cadastra, vira admin via troca de papel por outro admin).
 * "Esqueci senha" **aponta pro `/forgot-password` do cliente** — é a
 * mesma senha, da mesma conta, nos dois painéis (não existe um
 * ResetPasswordUseCase "admin" separado), então recuperar senha é
 * característica da conta, não do painel; pedido explícito do usuário
 * em 2026-08-15 depois de reconsiderar. Liga `data-panel="admin"` já
 * no `ngOnInit` (antes até do shell interno existir) pra o formulário
 * já nascer com a paleta preta.
 */
@Component({
  selector: 'app-admin-login-page',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, TranslocoModule, AdminBrandPanelComponent],
  templateUrl: './admin-login-page.component.html',
  styleUrl: './admin-login-page.component.css',
})
export class AdminLoginPageComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  ngOnInit(): void {
    document.documentElement.dataset['panel'] = 'admin';
  }

  ngOnDestroy(): void {
    delete document.documentElement.dataset['panel'];
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Autentica via AdminLoginUseCase (backend rejeita contas
   * sem role=admin com a mesma resposta de credenciais inválidas) e
   * redireciona pro Painel Admin em caso de sucesso.
   */
  submit(): void {
    if (this.form.invalid || this.submitting()) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    this.authService.loginAdmin(this.form.getRawValue()).subscribe({
      next: () => this.router.navigateByUrl('/admin/overview'),
      error: () => {
        this.submitting.set(false);
        this.errorMessage.set('admin.login.invalidCredentials');
      },
    });
  }
}
