import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';
import { MessageService } from 'primeng/api';
import { Subscription, interval, switchMap, takeWhile } from 'rxjs';
import type { EvolutionInstance } from '@amezia/shared-types';

import { EvolutionInstancesService } from '../../data-access/evolution-instances.service';
import { EvolutionInstanceCardComponent } from '../../ui/evolution-instance-card/evolution-instance-card.component';
import { WebhookConfigCardComponent } from '../../ui/webhook-config-card/webhook-config-card.component';

const POLL_INTERVAL_MS = 3000;

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-15
 * Descrição: Tela WhatsApp do Admin (build-context-06 §3.3) — MVP1
 * opera com no máximo uma instância ativa por vez, então esta página
 * sempre trabalha com `instances()[0]` (ou o estado vazio, com o
 * formulário de criação, se nenhuma existir ainda). Enquanto
 * `status='connecting'`, faz polling em `GET .../{public_id}` a cada
 * 3s até conectar ou o QR expirar (§3.3) — para sozinho nos dois casos.
 * Escopo reduzido do protótipo: sem uptime%/taxa de resposta% (exigem
 * observabilidade não especificada), sem editor de "mensagem de
 * boas-vindas", sem tabela de usuários com WhatsApp ativo (fora do
 * modelo de dados do MVP1).
 */
@Component({
  selector: 'app-admin-whatsapp-page',
  standalone: true,
  imports: [ReactiveFormsModule, TranslocoModule, EvolutionInstanceCardComponent, WebhookConfigCardComponent],
  templateUrl: './admin-whatsapp-page.component.html',
  styleUrl: './admin-whatsapp-page.component.css',
})
export class AdminWhatsappPageComponent implements OnInit, OnDestroy {
  private readonly evolutionService = inject(EvolutionInstancesService);
  private readonly fb = inject(FormBuilder);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);
  private pollSubscription: Subscription | null = null;

  readonly loading = this.evolutionService.loading;
  readonly error = this.evolutionService.error;

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: MVP1 opera com no máximo uma instância ativa por vez —
   * sempre lê a primeira da listagem, `null` antes de carregar ou
   * quando nenhuma existe ainda (aciona o formulário de criação).
   */
  protected readonly instance = computed<EvolutionInstance | null>(
    () => this.evolutionService.instances().at(0) ?? null,
  );
  protected readonly creating = signal(false);
  protected readonly actionPending = signal(false);
  protected readonly createError = signal<string | null>(null);

  protected readonly createForm = this.fb.nonNullable.group({
    name: ['', Validators.required],
    webhook_url: ['', Validators.required],
  });

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Indica se um campo do formulário de criação deve exibir
   * erro inline — só depois de tocado (evita mensagem de erro na
   * primeira renderização, antes do usuário interagir). Bug real
   * reportado pelo usuário: `markAllAsTouched()` já rodava em
   * `createInstance()`, mas o template nunca lia `invalid`/`touched` de
   * nenhum controle, então o formulário ficava mudo sobre qual campo
   * faltava preencher.
   */
  protected fieldInvalid(name: 'name' | 'webhook_url'): boolean {
    const control = this.createForm.get(name);
    return !!control && control.invalid && control.touched;
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Carrega a(s) instância(s) ao montar a página.
   */
  ngOnInit(): void {
    this.evolutionService.load();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Cancela o polling em andamento ao sair da página — sem
   * isso, o `interval` continuaria rodando e chamando a API mesmo com
   * o componente já destruído.
   */
  ngOnDestroy(): void {
    this._stopPolling();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-16
   * Descrição: Registra a instância + configura o webhook na Evolution
   * API (CreateEvolutionInstanceUseCase) — mostra o erro traduzido em
   * caso de falha (nome duplicado ou API não configurada). Toast de
   * sucesso (build-context-13) — erro já tinha mensagem inline
   * (`createError`), sucesso ficava mudo (só o formulário sumindo,
   * substituído pelo card da instância).
   */
  protected createInstance(): void {
    if (this.createForm.invalid || this.creating()) {
      this.createForm.markAllAsTouched();
      return;
    }
    this.creating.set(true);
    this.createError.set(null);
    this.evolutionService.create(this.createForm.getRawValue()).subscribe({
      next: () => {
        this.creating.set(false);
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('toasts.successTitle'),
          detail: this.transloco.translate('toasts.whatsapp.instanceCreated'),
        });
      },
      error: (error: unknown) => {
        this.creating.set(false);
        this.createError.set(this._extractErrorMessage(error));
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Mapeia o status HTTP pra uma chave de tradução própria
   * (409 nome duplicado, 503 Evolution API não configurada) — nunca
   * exibe o texto cru do `detail` do backend (sempre em inglês, RN-10)
   * direto na UI. Sem isso, uma falha na criação só reabilitava o botão
   * sem explicar o motivo ao operador (bug real, encontrado testando
   * sem EVOLUTION_API_URL configurada em 2026-08-15).
   */
  private _extractErrorMessage(error: unknown): string {
    const status = error && typeof error === 'object' && 'status' in error ? (error as { status: unknown }).status : null;
    if (status === 409) {
      return 'admin.whatsapp.createFailedDuplicate';
    }
    if (status === 503) {
      return 'admin.whatsapp.createFailedUnavailable';
    }
    return 'admin.whatsapp.createFailed';
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Inicia o pareamento (QR code) e dispara o polling de
   * status enquanto `connecting`. Toast de erro (build-context-13) —
   * antes essa falha ficava muda, só reabilitando o botão.
   */
  protected connect(): void {
    const current = this.instance();
    if (!current || this.actionPending()) {
      return;
    }
    this.actionPending.set(true);
    this.evolutionService.connect(current.public_id).subscribe({
      next: (updated) => {
        this.actionPending.set(false);
        this._startPolling(updated.public_id);
      },
      error: () => {
        this.actionPending.set(false);
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('toasts.errorTitle'),
          detail: this.transloco.translate('toasts.whatsapp.connectError'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Refresh manual de status/telefone — complementar aos
   * eventos de webhook. Toast de sucesso/erro (build-context-13) —
   * antes essa ação ficava muda nos dois casos.
   */
  protected sync(): void {
    const current = this.instance();
    if (!current || this.actionPending()) {
      return;
    }
    this.actionPending.set(true);
    this.evolutionService.sync(current.public_id).subscribe({
      next: () => {
        this.actionPending.set(false);
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('toasts.successTitle'),
          detail: this.transloco.translate('toasts.whatsapp.synced'),
        });
      },
      error: () => {
        this.actionPending.set(false);
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('toasts.errorTitle'),
          detail: this.transloco.translate('toasts.whatsapp.syncError'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Logout da sessão pareada — também para qualquer polling
   * em andamento (não faz sentido continuar checando um QR que não
   * existe mais). Toast de sucesso/erro (build-context-13) — ação
   * destrutiva que antes não confirmava nada ao operador.
   */
  protected disconnect(): void {
    const current = this.instance();
    if (!current || this.actionPending()) {
      return;
    }
    this.actionPending.set(true);
    this.evolutionService.disconnect(current.public_id).subscribe({
      next: () => {
        this.actionPending.set(false);
        this._stopPolling();
        this.messageService.add({
          severity: 'success',
          summary: this.transloco.translate('toasts.successTitle'),
          detail: this.transloco.translate('toasts.whatsapp.disconnected'),
        });
      },
      error: () => {
        this.actionPending.set(false);
        this.messageService.add({
          severity: 'error',
          summary: this.transloco.translate('toasts.errorTitle'),
          detail: this.transloco.translate('toasts.whatsapp.disconnectError'),
        });
      },
    });
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Faz polling em GET .../{public_id} a cada 3s enquanto o
   * status continuar `connecting` e o QR ainda não tiver expirado —
   * `takeWhile(..., true)` inclui o último valor (o que já disparou a
   * condição de parada) antes de completar, pro card renderizar o
   * estado final (conectado ou QR expirado) sem esperar mais um tick.
   */
  private _startPolling(publicId: string): void {
    this._stopPolling();
    this.pollSubscription = interval(POLL_INTERVAL_MS)
      .pipe(
        switchMap(() => this.evolutionService.getByPublicId(publicId)),
        takeWhile((updated) => updated.status === 'connecting' && this._qrStillValid(updated), true),
      )
      .subscribe();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Compara `qr_code_expires_at` com o relógio local — usado
   * pra decidir se o polling deve continuar ou parar (QR expirado).
   */
  private _qrStillValid(instance: EvolutionInstance): boolean {
    if (!instance.qr_code_expires_at) {
      return false;
    }
    return new Date(instance.qr_code_expires_at).getTime() > Date.now();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-15
   * Descrição: Cancela a subscription de polling ativa, se houver.
   */
  private _stopPolling(): void {
    this.pollSubscription?.unsubscribe();
    this.pollSubscription = null;
  }
}
