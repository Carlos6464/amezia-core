import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoModule } from '@jsverse/transloco';
import type { BillingCycle, PaidPlan } from '@amezia/shared-types';

import { PlanPricesService } from '../../data-access/plan-prices.service';

const PAID_PLANS: PaidPlan[] = ['pro', 'premium'];
const BILLING_CYCLES: BillingCycle[] = ['monthly', 'annual'];

/**
 * Autor: Carlos Adriano
 * Data: 2026-09-10
 * Descrição: Tela de cadastro de preço no Admin — separada da listagem
 * (`admin-plans-page`) a pedido do usuário, que quis "uma tela pra
 * lista e outra pro add/edit". `POST /admin/plan-prices/{plan}` sempre
 * cria um Price novo no Stripe pra combinação (plano, ciclo) e arquiva
 * o anterior automaticamente — um Price do Stripe é imutável em valor,
 * então não existe "editar" de fato, só substituir (mesmo conceito de
 * "cadastro" e "edição" aqui: o formulário é o mesmo pros dois casos).
 * Ao salvar, volta pra listagem (que recarrega o catálogo ao montar).
 */
@Component({
  selector: 'app-admin-plan-price-form-page',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, TranslocoModule],
  templateUrl: './admin-plan-price-form-page.component.html',
  styleUrl: './admin-plan-price-form-page.component.css',
})
export class AdminPlanPriceFormPageComponent {
  private readonly planPricesService = inject(PlanPricesService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);

  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);

  protected readonly plans = PAID_PLANS;
  protected readonly cycles = BILLING_CYCLES;

  protected readonly priceForm = this.fb.nonNullable.group({
    plan: this.fb.nonNullable.control<PaidPlan>('pro', Validators.required),
    billing_cycle: this.fb.nonNullable.control<BillingCycle>('monthly', Validators.required),
    amount: ['', [Validators.required, Validators.pattern(/^\d+([.,]\d{1,2})?$/)]],
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Indica se o campo de valor deve exibir erro inline — só
   * depois de tocado, mesmo padrão de `admin-whatsapp-page`.
   */
  protected fieldInvalid(): boolean {
    const control = this.priceForm.get('amount');
    return !!control && control.invalid && control.touched;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-10
   * Descrição: Converte o valor digitado em reais (aceita vírgula ou
   * ponto decimal, ex. "19,90") para centavos e envia
   * `POST /admin/plan-prices/{plan}` — o backend cria um Price novo no
   * Stripe e arquiva o anterior da mesma combinação (plano, ciclo)
   * automaticamente. Volta pra listagem ao concluir.
   */
  protected submitPrice(): void {
    if (this.priceForm.invalid || this.saving()) {
      this.priceForm.markAllAsTouched();
      return;
    }
    const { plan, billing_cycle, amount } = this.priceForm.getRawValue();
    const unitAmountCents = Math.round(Number(amount.replace(',', '.')) * 100);

    this.saving.set(true);
    this.formError.set(null);
    this.planPricesService.createOrUpdate(plan, { billing_cycle, unit_amount_cents: unitAmountCents }).subscribe({
      next: () => {
        this.saving.set(false);
        this.router.navigateByUrl('/admin/plans');
      },
      error: () => {
        this.saving.set(false);
        this.formError.set('admin.plans.form.saveFailed');
      },
    });
  }
}
