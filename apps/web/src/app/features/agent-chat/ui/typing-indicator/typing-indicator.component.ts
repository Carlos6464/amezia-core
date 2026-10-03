import { Component } from '@angular/core';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-11
 * Descrição: Indicador "digitando" (três pontos animados) exibido no
 * lugar da próxima bolha `assistant` enquanto `waitingResponse()` está
 * ativo (build-context-04 §3.2) — componente puramente declarativo, sem
 * inputs/outputs.
 */
@Component({
  selector: 'app-typing-indicator',
  standalone: true,
  templateUrl: './typing-indicator.component.html',
  styleUrl: './typing-indicator.component.css',
})
export class TypingIndicatorComponent {}
