import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.security.jwt_service import JwtService
from src.presentation.api.v1.router import router as v1_router
from src.presentation.websocket.manager import manager
from src.presentation.websocket.redis_subscriber import listen_for_ws_events


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Inicia a task de background que assina a ponte Redis
    Pub/Sub (`ws:user:*`, build-context-04 §2.8) junto com o processo
    `api`, e a cancela de forma limpa no shutdown. Primeiro `lifespan`
    do projeto — antes não havia nenhum trabalho de background a
    iniciar/encerrar junto do ciclo de vida da aplicação.
    """
    task = asyncio.create_task(listen_for_ws_events())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="Amezia API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-18
    Descrição: Healthcheck da API — `service` identifica a origem da
    resposta quando o mesmo endpoint é agregado num monitor com vários
    serviços.
    """
    return {"status": "ok", "service": "amezia-api"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Aceita a conexão WebSocket só se o JWT (?token=) for um
    access token válido (assinatura + type == "access" + expiração),
    associando-a ao user_id decodificado — autenticação real introduzida
    pelo build-context-01 (antes, qualquer JWT assinado era aceito).
    """
    payload = JwtService().decode(token, "access")
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id = payload["sub"]

    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
