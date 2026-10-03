import uuid
from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.user import User as UserModel
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _make_oauth_only_user(db_session: AsyncSession) -> tuple[UserModel, str]:
    """OAuth-only account (password_hash=None) — mesmo perfil que o bug real cobria."""
    from src.infrastructure.security.jwt_service import JwtService

    user_id = uuid.uuid4()
    model = UserModel(
        id=user_id,
        name="OAuth Only User",
        email=f"oauth-only-{user_id.hex[:12]}@example.com",
        password_hash=None,
        oauth_provider="google",
        oauth_id=f"google-{user_id.hex[:12]}",
        role="user",
        language="pt-BR",
    )
    db_session.add(model)
    await db_session.flush()
    token = JwtService().create_access_token(user_id=str(user_id), role="user", language="pt-BR")
    return model, token


async def test_set_password_succeeds_for_oauth_only_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Conta só-OAuth (o bug real: Google vinculado, sem senha) consegue definir senha."""
    _, token = await _make_oauth_only_user(db_session)

    response = await client.post(
        "/api/v1/auth/me/password",
        json={"new_password": "new-secure-pass-123"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["has_password"] is True


async def test_set_password_rejects_account_that_already_has_password(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Conta que já tem senha local deve usar PATCH /me/password (troca), não este endpoint."""
    _, token = await make_user()

    response = await client.post(
        "/api/v1/auth/me/password",
        json={"new_password": "new-secure-pass-123"},
        headers=auth_headers(token),
    )

    assert response.status_code == 400


async def test_get_me_reports_has_password_false_for_oauth_only_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, token = await _make_oauth_only_user(db_session)

    response = await client.get("/api/v1/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["has_password"] is False


async def test_get_me_reports_has_password_true_for_local_account(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()

    response = await client.get("/api/v1/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["has_password"] is True
