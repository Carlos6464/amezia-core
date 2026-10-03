import { Injectable } from '@angular/core';

const STORAGE_KEY = 'amezia-theme';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-08
 * Descrição: Alterna `data-theme` (dark/light) na raiz do documento e
 * persiste a escolha — usado pelo botão flutuante de tema presente em
 * todas as telas do design system (protótipos register-form/settings-profile).
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Aplica a preferência salva no `localStorage`, se houver.
   * Sem preferência salva, o padrão é light (tokens em styles.css) — não
   * segue `prefers-color-scheme` de propósito, para o primeiro acesso
   * ficar previsível independente do SO/browser do usuário.
   */
  init(): void {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') {
      document.documentElement.dataset['theme'] = stored;
    }
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-08
   * Descrição: Alterna entre dark/light e persiste a escolha — chamado
   * pelo botão de tema presente em todas as telas do design system.
   */
  toggle(): void {
    const current = document.documentElement.dataset['theme'] === 'dark' ? 'dark' : 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset['theme'] = next;
    localStorage.setItem(STORAGE_KEY, next);
  }
}
