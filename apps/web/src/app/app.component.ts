import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { SwUpdate, VersionReadyEvent } from '@angular/service-worker';
import { TranslocoService } from '@jsverse/transloco';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { filter } from 'rxjs';
import { LanguageService } from './core/i18n/language.service';
import { ThemeService } from './core/theme/theme.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, ToastModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit {
  private readonly languageService = inject(LanguageService);
  private readonly themeService = inject(ThemeService);
  private readonly swUpdate = inject(SwUpdate);
  private readonly messageService = inject(MessageService);
  private readonly transloco = inject(TranslocoService);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Inicializa idioma (fallback do navegador, até o login
   * trazer a preferência do perfil) e tema (localStorage) antes de
   * qualquer tela renderizar.
   */
  ngOnInit(): void {
    this.languageService.initFromBrowser();
    this.themeService.init();
    this.listenForAppUpdates();
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-09-15
   * Descrição: Recarrega o app sozinho quando o Service Worker detecta
   * uma versão nova publicada (`VERSION_READY`) — sem isso, o PWA
   * continua servindo o bundle antigo em cache indefinidamente pra
   * quem já tinha a aba aberta, mesmo depois de um deploy novo (o
   * usuário só veria a mudança fechando e reabrindo a aba manualmente
   * várias vezes, achando que a correção não tinha sido aplicada de
   * verdade — foi exatamente isso que aconteceu com o botão
   * "Personalizar" do Dashboard, ver `DIARIO.md` 2026-09-15). Mostra um
   * toast breve antes de recarregar, pra não sumir a tela do nada.
   */
  private listenForAppUpdates(): void {
    if (!this.swUpdate.isEnabled) {
      return;
    }
    this.swUpdate.versionUpdates
      .pipe(filter((event): event is VersionReadyEvent => event.type === 'VERSION_READY'))
      .subscribe(() => {
        this.messageService.add({
          severity: 'info',
          summary: this.transloco.translate('app.updateAvailable.title'),
          detail: this.transloco.translate('app.updateAvailable.detail'),
          life: 3000,
        });
        window.setTimeout(() => document.location.reload(), 1500);
      });
  }
}
