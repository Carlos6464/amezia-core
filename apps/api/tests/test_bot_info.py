import uuid
from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.shared.value_objects import PublicId
from src.infrastructure.database.models.evolution_instance import (
    EvolutionInstance as EvolutionInstanceModel,
)
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _make_evolution_instance(
    db_session: AsyncSession, **overrides: Any
) -> EvolutionInstanceModel:
    """Mesmo padrão de `test_admin_evolution.py::_make_evolution_instance`."""
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


async def test_bot_info_without_active_instance_is_unavailable(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()

    response = await client.get("/api/v1/bot/info", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["is_available"] is False
    assert body["phone_number"] is None


async def test_bot_info_returns_active_instance_phone_number(
    client: AsyncClient, make_user: Callable[..., Any], db_session: AsyncSession
) -> None:
    _, token = await make_user()
    await _make_evolution_instance(
        db_session, is_active=True, status="connected", phone_number="5511999990000"
    )

    response = await client.get("/api/v1/bot/info", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["is_available"] is True
    assert body["phone_number"] == "5511999990000"


async def test_bot_info_connecting_instance_is_not_available(
    client: AsyncClient, make_user: Callable[..., Any], db_session: AsyncSession
) -> None:
    """Instância com número já vinculado mas ainda não conectada — `is_available=False`."""
    _, token = await make_user()
    await _make_evolution_instance(
        db_session, is_active=True, status="connecting", phone_number="5511999990000"
    )

    response = await client.get("/api/v1/bot/info", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["is_available"] is False


async def test_bot_info_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/bot/info")

    assert response.status_code == 401
