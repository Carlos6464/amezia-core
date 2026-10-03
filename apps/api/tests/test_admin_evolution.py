import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.evolution.exceptions import EvolutionInstanceAlreadyExistsError
from src.domain.shared.value_objects import PublicId
from src.infrastructure.database.models.evolution_instance import (
    EvolutionInstance as EvolutionInstanceModel,
)
from src.infrastructure.whatsapp.evolution_client import get_evolution_api_client
from src.presentation.main import app
from tests.conftest import FakeArqPool, auth_headers

pytestmark = pytest.mark.asyncio


class FakeEvolutionApiClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Substituto de EvolutionApiClient para testes — nunca bate
    na Evolution API real, só grava as chamadas em memória. Mesmo
    espírito de FakeArqPool/FakeRedisClient (conftest.py).
    """

    def __init__(self) -> None:
        self.created: list[str] = []
        self.webhooks: dict[str, str] = {}
        self.deleted: list[str] = []
        self.logged_out: list[str] = []
        self.connect_qr_code: str | None = "base64-qr-code-data"
        self.connection_state: tuple[str, str | None] = ("open", "5511999999999")
        self.already_exists_remotely = False

    async def create_instance(self, name: str) -> None:
        if self.already_exists_remotely:
            raise EvolutionInstanceAlreadyExistsError(name)
        self.created.append(name)

    async def set_webhook(self, name: str, webhook_url: str) -> None:
        self.webhooks[name] = webhook_url

    async def connect_instance(self, name: str) -> str | None:
        return self.connect_qr_code

    async def get_connection_state(self, name: str) -> tuple[str, str | None]:
        return self.connection_state

    async def logout_instance(self, name: str) -> None:
        self.logged_out.append(name)

    async def delete_instance(self, name: str) -> None:
        self.deleted.append(name)


@pytest_asyncio.fixture
async def fake_evolution_client() -> AsyncGenerator[FakeEvolutionApiClient, None]:
    fake = FakeEvolutionApiClient()
    app.dependency_overrides[get_evolution_api_client] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_evolution_api_client, None)


async def _make_evolution_instance(
    db_session: AsyncSession, **overrides: Any
) -> EvolutionInstanceModel:
    """
    `is_active=True` primeiro desativa qualquer instância ativa já
    existente na mesma transação (`ux_evolution_instances_single_active`
    permite só uma) — necessário porque este projeto não tem banco de
    teste separado (`tests/conftest.py`): o Postgres de dev pode ter uma
    instância real ativa (ex.: vinculada manualmente numa sessão de
    depuração, 2026-08-16), e essa `UPDATE` só existe dentro do savepoint
    do teste, revertida no teardown — nunca afeta o dado real fora dele.
    """
    defaults: dict[str, Any] = {
        "public_id": str(PublicId.generate()),
        "name": f"instance-{uuid.uuid4().hex[:8]}",
        "webhook_url": "https://api.amezia.app/api/v1/webhook/evolution",
        "webhook_secret": "test-webhook-secret",
        "status": "disconnected",
        "is_active": False,
    }
    defaults.update(overrides)
    if defaults["is_active"]:
        await db_session.execute(
            update(EvolutionInstanceModel)
            .where(EvolutionInstanceModel.is_active.is_(True))
            .values(is_active=False)
        )
    model = EvolutionInstanceModel(**defaults)
    db_session.add(model)
    await db_session.flush()
    return model


async def test_create_evolution_instance_success(
    client: AsyncClient,
    make_user: Callable[..., Any],
    fake_evolution_client: FakeEvolutionApiClient,
) -> None:
    """
    CreateEvolutionInstanceUseCase sincroniza logo após criar (2026-08-16,
    portado do projeto irmão) — uma instância recém-criada, ainda não
    pareada, deve refletir isso na Evolution real (`close`), diferente do
    default do fake (usado pelos testes de connect/sync).
    """
    _, admin_token = await make_user(role="admin")
    fake_evolution_client.connection_state = ("close", None)

    response = await client.post(
        "/api/v1/admin/evolution-instances",
        json={"name": "amezia-bot-prod", "webhook_url": "https://api.amezia.app/api/v1/webhook/evolution"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "amezia-bot-prod"
    assert body["status"] == "disconnected"
    assert body["webhook_secret_masked"].endswith(body["webhook_secret_masked"][-4:])
    assert "amezia-bot-prod" in fake_evolution_client.created
    assert "instance=" in fake_evolution_client.webhooks["amezia-bot-prod"]
    assert "secret=" in fake_evolution_client.webhooks["amezia-bot-prod"]


async def test_create_evolution_instance_already_existing_remotely_links_instead_of_failing(
    client: AsyncClient,
    make_user: Callable[..., Any],
    fake_evolution_client: FakeEvolutionApiClient,
) -> None:
    """
    Instância já existente do lado da Evolution (ex.: criada direto no
    painel dela) não deve falhar a criação local — vincula em vez disso:
    ainda configura o webhook nela e sincroniza o estado real (conectada,
    com número), em vez de nascer como um registro órfão/desconectado.
    """
    _, admin_token = await make_user(role="admin")
    fake_evolution_client.already_exists_remotely = True
    fake_evolution_client.connection_state = ("open", "5522992217690")
    instance_name = f"already-remote-{uuid.uuid4().hex[:8]}"

    response = await client.post(
        "/api/v1/admin/evolution-instances",
        json={"name": instance_name, "webhook_url": "https://api.amezia.app/api/v1/webhook/evolution"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == instance_name
    assert body["status"] == "connected"
    assert body["phone_number"] == "5522992217690"
    assert instance_name not in fake_evolution_client.created
    assert "instance=" in fake_evolution_client.webhooks[instance_name]


async def test_create_evolution_instance_duplicate_name_conflicts(
    client: AsyncClient,
    make_user: Callable[..., Any],
    fake_evolution_client: FakeEvolutionApiClient,
    db_session: AsyncSession,
) -> None:
    _, admin_token = await make_user(role="admin")
    await _make_evolution_instance(db_session, name="already-taken")

    response = await client.post(
        "/api/v1/admin/evolution-instances",
        json={"name": "already-taken", "webhook_url": "https://api.amezia.app/api/v1/webhook/evolution"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 409


async def test_list_evolution_instances_paginated(
    client: AsyncClient, make_user: Callable[..., Any], db_session: AsyncSession
) -> None:
    _, admin_token = await make_user(role="admin")
    await _make_evolution_instance(db_session)
    await _make_evolution_instance(db_session)

    response = await client.get(
        "/api/v1/admin/evolution-instances", headers=auth_headers(admin_token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2


async def test_get_evolution_instance_not_found(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, admin_token = await make_user(role="admin")

    response = await client.get(
        f"/api/v1/admin/evolution-instances/{PublicId.generate()}", headers=auth_headers(admin_token)
    )

    assert response.status_code == 404


async def test_activating_instance_deactivates_previously_active_one(
    client: AsyncClient,
    make_user: Callable[..., Any],
    fake_evolution_client: FakeEvolutionApiClient,
    db_session: AsyncSession,
) -> None:
    _, admin_token = await make_user(role="admin")
    currently_active = await _make_evolution_instance(db_session, is_active=True)
    new_instance = await _make_evolution_instance(db_session, is_active=False)

    response = await client.patch(
        f"/api/v1/admin/evolution-instances/{new_instance.public_id}",
        json={"is_active": True},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is True

    check = await client.get(
        f"/api/v1/admin/evolution-instances/{currently_active.public_id}",
        headers=auth_headers(admin_token),
    )
    assert check.json()["is_active"] is False


async def test_delete_evolution_instance(
    client: AsyncClient,
    make_user: Callable[..., Any],
    fake_evolution_client: FakeEvolutionApiClient,
    db_session: AsyncSession,
) -> None:
    _, admin_token = await make_user(role="admin")
    instance = await _make_evolution_instance(db_session)

    response = await client.delete(
        f"/api/v1/admin/evolution-instances/{instance.public_id}", headers=auth_headers(admin_token)
    )

    assert response.status_code == 204
    assert instance.name in fake_evolution_client.deleted


async def test_connect_evolution_instance_sets_qr_code_and_connecting_status(
    client: AsyncClient,
    make_user: Callable[..., Any],
    fake_evolution_client: FakeEvolutionApiClient,
    db_session: AsyncSession,
) -> None:
    _, admin_token = await make_user(role="admin")
    instance = await _make_evolution_instance(db_session)

    response = await client.post(
        f"/api/v1/admin/evolution-instances/{instance.public_id}/connect",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "connecting"
    assert body["qr_code"] == "base64-qr-code-data"
    assert body["qr_code_expires_at"] is not None


async def test_sync_evolution_instance_updates_status_and_phone(
    client: AsyncClient,
    make_user: Callable[..., Any],
    fake_evolution_client: FakeEvolutionApiClient,
    db_session: AsyncSession,
) -> None:
    _, admin_token = await make_user(role="admin")
    instance = await _make_evolution_instance(db_session)
    fake_evolution_client.connection_state = ("open", "5511988887777")

    response = await client.post(
        f"/api/v1/admin/evolution-instances/{instance.public_id}/sync",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "connected"
    assert body["phone_number"] == "5511988887777"
    assert body["connected_at"] is not None


async def test_disconnect_evolution_instance(
    client: AsyncClient,
    make_user: Callable[..., Any],
    fake_evolution_client: FakeEvolutionApiClient,
    db_session: AsyncSession,
) -> None:
    _, admin_token = await make_user(role="admin")
    instance = await _make_evolution_instance(db_session, status="connected", phone_number=None)

    response = await client.post(
        f"/api/v1/admin/evolution-instances/{instance.public_id}/disconnect",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disconnected"
    assert instance.name in fake_evolution_client.logged_out


async def test_webhook_evolution_valid_request_enqueues_job(
    client: AsyncClient, db_session: AsyncSession, fake_arq_pool: FakeArqPool
) -> None:
    instance = await _make_evolution_instance(db_session)
    payload = {"event": "SEND_MESSAGE", "instance": instance.name, "data": {}}

    response = await client.post(
        "/api/v1/webhook/evolution",
        params={"instance": instance.public_id, "secret": instance.webhook_secret},
        json=payload,
    )

    assert response.status_code == 200
    assert fake_arq_pool.enqueued == [("send_message", (instance.id, payload))]


async def test_webhook_evolution_lowercase_dotted_event_still_enqueues_job(
    client: AsyncClient, db_session: AsyncSession, fake_arq_pool: FakeArqPool
) -> None:
    """
    A instância Evolution real deste projeto manda `event` em minúsculo
    com ponto (`"messages.upsert"`), não `SCREAMING_SNAKE_CASE`
    (`"MESSAGES_UPSERT"`) como `EvolutionApiClient.set_webhook` usa para
    *assinar* os eventos — bug real encontrado em produção local
    (2026-08-16, o bot nunca respondia a nenhuma mensagem). `event` deve
    ser normalizado antes de bater contra `_EVENT_JOB_MAP`.
    """
    instance = await _make_evolution_instance(db_session)
    payload = {"event": "messages.upsert", "instance": instance.name, "data": {}}

    response = await client.post(
        "/api/v1/webhook/evolution",
        params={"instance": instance.public_id, "secret": instance.webhook_secret},
        json=payload,
    )

    assert response.status_code == 200
    assert fake_arq_pool.enqueued == [("dispatch_message_to_bot", (instance.id, payload))]


async def test_webhook_evolution_wrong_secret_returns_401_without_enqueuing(
    client: AsyncClient, db_session: AsyncSession, fake_arq_pool: FakeArqPool
) -> None:
    instance = await _make_evolution_instance(db_session)

    response = await client.post(
        "/api/v1/webhook/evolution",
        params={"instance": instance.public_id, "secret": "wrong-secret"},
        json={"event": "SEND_MESSAGE"},
    )

    assert response.status_code == 401
    assert fake_arq_pool.enqueued == []


async def test_webhook_evolution_unknown_instance_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/webhook/evolution",
        params={"instance": str(PublicId.generate()), "secret": "whatever"},
        json={"event": "SEND_MESSAGE"},
    )

    assert response.status_code == 404


async def test_webhook_evolution_unknown_event_still_returns_200_without_enqueuing(
    client: AsyncClient, db_session: AsyncSession, fake_arq_pool: FakeArqPool
) -> None:
    instance = await _make_evolution_instance(db_session)

    response = await client.post(
        "/api/v1/webhook/evolution",
        params={"instance": instance.public_id, "secret": instance.webhook_secret},
        json={"event": "SOME_UNKNOWN_EVENT"},
    )

    assert response.status_code == 200
    assert fake_arq_pool.enqueued == []
