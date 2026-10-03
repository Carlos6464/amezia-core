import httpx
from fastapi import HTTPException, status

from src.domain.evolution.exceptions import EvolutionInstanceAlreadyExistsError
from src.infrastructure.config import get_settings

_WEBHOOK_EVENTS = ["CONNECTION_UPDATE", "QRCODE_UPDATED", "SEND_MESSAGE", "MESSAGES_UPSERT"]


class EvolutionApiError(Exception):
    pass


class EvolutionApiClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Client HTTP para a Evolution API self-hosted (WhatsApp,
    build-context-06 §2 e §2.3) — autenticado via header `apikey`
    (EVOLUTION_API_KEY) contra EVOLUTION_API_URL. Cada método traduz
    falha de rede/HTTP em EvolutionApiError, para os use cases nunca
    lidarem com exceções do `httpx` diretamente.
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_API_KEY:
            raise RuntimeError("EVOLUTION_API_URL/EVOLUTION_API_KEY is not configured")
        self._base_url = settings.EVOLUTION_API_URL.rstrip("/")
        self._headers = {"apikey": settings.EVOLUTION_API_KEY}

    async def create_instance(self, name: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Registra a instância na Evolution API
        (`POST /instance/create`) — só cria o registro, sem parear ainda
        (pareamento é `connect_instance`, chamado à parte). Levanta
        `EvolutionInstanceAlreadyExistsError` em `403` com "already in
        use"/"already exists" no corpo — a instância já existe do lado
        da Evolution (ex.: criada direto no painel dela), caso comum que
        `CreateEvolutionInstanceUseCase` trata vinculando em vez de
        falhar (portado do projeto irmão, 2026-08-16).
        """
        async with self._client() as client:
            response = await client.post(
                "/instance/create",
                json={"instanceName": name, "qrcode": True, "integration": "WHATSAPP-BAILEYS"},
            )
            if response.status_code == 403:
                body = response.text.lower()
                if "already in use" in body or "already exists" in body:
                    raise EvolutionInstanceAlreadyExistsError(name)
            await self._raise_for_status(response)

    async def connect_instance(self, name: str) -> str | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Inicia o pareamento (`GET /instance/connect/{name}`) —
        devolve o payload do QR code em base64, ou None se a instância já
        estiver conectada (a Evolution API não emite QR nesse caso).
        """
        async with self._client() as client:
            response = await client.get(f"/instance/connect/{name}")
            await self._raise_for_status(response)
            data = response.json()
            return data.get("base64")

    async def get_connection_state(self, name: str) -> tuple[str, str | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Consulta o estado atual (`GET /instance/connectionState/{name}`)
        — devolve (estado bruto `open`/`close`/`connecting`, número de
        telefone conectado ou None). O estado é traduzido para
        ConnectionStatus pelo use case chamador (SyncEvolutionInstanceUseCase),
        não aqui. O número vem do JID (`5511999999999@s.whatsapp.net`) que
        a Evolution API expõe em `instance.owner` só quando conectada —
        extraído até o `@`.
        """
        async with self._client() as client:
            response = await client.get(f"/instance/connectionState/{name}")
            await self._raise_for_status(response)
            data = response.json().get("instance", {})
            state = data.get("state", "close")
            owner = data.get("owner")
            phone_number = owner.split("@")[0] if owner else None
            return state, phone_number

    async def logout_instance(self, name: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Encerra a sessão pareada (`DELETE /instance/logout/{name}`)
        sem remover o registro da instância — ela volta a poder ser
        conectada de novo depois.
        """
        async with self._client() as client:
            response = await client.delete(f"/instance/logout/{name}")
            await self._raise_for_status(response)

    async def delete_instance(self, name: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Remove a instância por completo da Evolution API
        (`DELETE /instance/delete/{name}`) — chamado antes de apagar o
        registro local (DeleteEvolutionInstanceUseCase).
        """
        async with self._client() as client:
            response = await client.delete(f"/instance/delete/{name}")
            await self._raise_for_status(response)

    async def set_webhook(self, name: str, webhook_url: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Configura o webhook da instância (`POST /webhook/set/{name}`)
        com os 4 eventos que este módulo processa (build-context-06 §2.5)
        — chamado na criação e sempre que `webhook_url` é atualizada.
        `enabled`/`byEvents` são obrigatórios na instância Evolution real
        deste projeto (`400 "webhook requires property \"enabled\""` sem
        eles, confirmado em 2026-08-16) — a Evolution não assume default
        pra esse campo.
        """
        async with self._client() as client:
            response = await client.post(
                f"/webhook/set/{name}",
                json={
                    "webhook": {
                        "enabled": True,
                        "url": webhook_url,
                        "byEvents": False,
                        "events": _WEBHOOK_EVENTS,
                    }
                },
            )
            await self._raise_for_status(response)

    async def send_text(self, name: str, phone: str, text: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Envia uma mensagem de texto (`POST /message/sendText/{name}`,
        build-context-07 §2.6, passo 9) — usado pelo orquestrador do Bot
        WhatsApp para responder ao usuário. `phone` é o número puro
        (dígitos, sem `@s.whatsapp.net`) — a Evolution API monta o JID
        internamente. Tenta o payload "moderno" primeiro; em `400` com
        `textMessage` ou (`text` + `property`) no corpo — assinatura de
        erro de versões da Evolution que só aceitam o formato "legado" —
        tenta de novo nesse formato. Bug real de versão, documentado no
        projeto irmão (`/home/adriano/Documentos/projetos/Amezia`,
        DIARIO.md), portado aqui em 2026-08-15.
        """
        modern_payload = {"number": phone, "text": text, "delay": 400, "linkPreview": True}
        legacy_payload = {
            "number": phone,
            "textMessage": {"text": text},
            "options": {"delay": 400, "presence": "composing", "linkPreview": True},
        }
        async with self._client() as client:
            response = await client.post(f"/message/sendText/{name}", json=modern_payload)
            if response.status_code == 400 and (
                "textMessage" in response.text
                or ("text" in response.text and "property" in response.text)
            ):
                response = await client.post(f"/message/sendText/{name}", json=legacy_payload)
            await self._raise_for_status(response)

    def _client(self) -> httpx.AsyncClient:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Fábrica do client HTTP async, com base_url/headers/timeout
        já configurados — cada método abre e fecha o próprio client (sem
        estado compartilhado entre chamadas).
        """
        return httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=15.0)

    async def _raise_for_status(self, response: httpx.Response) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Traduz qualquer status HTTP de erro em EvolutionApiError
        — os use cases só precisam tratar um tipo de exceção, nunca
        `httpx.HTTPStatusError` diretamente.
        """
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EvolutionApiError(
                f"Evolution API request failed: {response.status_code}"
            ) from exc


def get_evolution_api_client() -> EvolutionApiClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Dependency FastAPI (mesmo espírito de `get_arq_pool`) —
    permite os routers do Admin injetarem o client via `Depends` em vez
    de instanciar direto, para os testes trocarem por um fake
    (`app.dependency_overrides`) sem precisar configurar
    EVOLUTION_API_URL/EVOLUTION_API_KEY nem bater na Evolution API real.
    Traduz `RuntimeError` (env var ausente) em `HTTPException` 503 — sem
    isso, a exceção nasce durante a resolução da dependency, antes até
    do corpo da rota rodar, e vazava como 500 genérico (bug real,
    encontrado em 2026-08-15 testando a criação de instância sem
    EVOLUTION_API_URL configurada).
    """
    try:
        return EvolutionApiClient()
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
