import { Injectable, signal } from '@angular/core';
import { Subject } from 'rxjs';

const RECONNECT_DELAY_MS = 3000;

@Injectable({ providedIn: 'root' })
export class WebSocketService {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private currentToken: string | null = null;

  readonly connected = signal(false);
  readonly messages$ = new Subject<unknown>();

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-06
   * Descrição: Conecta no /ws da API autenticando via query param `token`
   * (JWT), com reconexão automática em caso de queda. Chamado após o login
   * a partir do build-context-01.
   */
  connect(token: string): void {
    this.currentToken = token;
    this.openSocket();
  }

  disconnect(): void {
    this.currentToken = null;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
    this.socket = null;
    this.connected.set(false);
  }

  send(message: unknown): void {
    this.socket?.send(JSON.stringify(message));
  }

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-11
   * Descrição: Fecha o socket atual antes de abrir um novo — `connect()`
   * pode ser chamado mais de uma vez com o processo já conectado (ex.:
   * restauração de sessão + login social próximos um do outro); sem
   * isso, a conexão antiga fica órfã (nunca fechada no cliente) e o
   * `ConnectionManager` do backend acumula uma entrada morta por
   * usuário até o socket antigo cair sozinho.
   */
  private openSocket(): void {
    if (!this.currentToken) {
      return;
    }

    this.socket?.close();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws?token=${this.currentToken}`;
    this.socket = new WebSocket(url);

    this.socket.onopen = () => this.connected.set(true);

    this.socket.onmessage = (event) => {
      this.messages$.next(JSON.parse(event.data));
    };

    this.socket.onclose = () => {
      this.connected.set(false);
      if (this.currentToken) {
        this.reconnectTimer = setTimeout(() => this.openSocket(), RECONNECT_DELAY_MS);
      }
    };
  }
}
