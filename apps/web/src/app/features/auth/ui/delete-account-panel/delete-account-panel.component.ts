import { Component, EventEmitter, Output, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslocoModule, TranslocoService } from '@jsverse/transloco';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Zona de perigo da tela de perfil — exige digitar "EXCLUIR"
 * para habilitar o botão de exclusão de conta (mesma fricção mínima do
 * protótipo settings-profile). Componente dumb: só emite `confirmed`,
 * quem chama DeleteAccountUseCase é a feature/profile-page.
 */
@Component({
  selector: 'app-delete-account-panel',
  standalone: true,
  imports: [FormsModule, TranslocoModule],
  templateUrl: './delete-account-panel.component.html',
  styleUrl: './delete-account-panel.component.css',
})
export class DeleteAccountPanelComponent {
  private readonly translocoService = inject(TranslocoService);

  confirmText = '';
  open = signal(false);

  @Output() confirmed = new EventEmitter<void>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Palavra de confirmação traduzida ("EXCLUIR"/"DELETE") —
   * getter (não Signal) porque é reavaliado a cada change detection,
   * refletindo troca de idioma em runtime sem lógica extra de subscription.
   */
  get confirmWord(): string {
    return this.translocoService.translate('auth.profile.danger.confirmWord');
  }
}
