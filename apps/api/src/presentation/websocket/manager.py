from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-06
        Descrição: Aceita a conexão WebSocket e registra sob o user_id extraído
        do JWT, permitindo múltiplas conexões simultâneas do mesmo usuário
        (ex: várias abas abertas).
        """
        await websocket.accept()
        self._connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        connections = self._connections.get(user_id)
        if not connections:
            return
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-06
        Descrição: Envia uma mensagem JSON para todas as conexões ativas de um
        usuário — usado pelo worker ARQ para entregar resultados assíncronos
        (respostas de IA, notificações) a partir do build-context-04.
        """
        for connection in self._connections.get(user_id, []):
            await connection.send_json(message)


manager = ConnectionManager()
