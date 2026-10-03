from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.category import Category as CategoryModel
from src.infrastructure.database.models.user import User as UserModel
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_list_categories_returns_seven_globals_for_new_user(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Novo usuário, sem privadas, sempre vê as 7 categorias de sistema (seed)."""
    _, token = await make_user()

    response = await client.get("/api/v1/categories", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 7
    assert all(category["scope"] == "global" for category in body)
    assert all(category["is_system"] is True for category in body)


async def test_create_private_category_appears_in_listing(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()

    create_response = await client.post(
        "/api/v1/categories",
        headers=auth_headers(token),
        json={"name": "Pets", "color": "#123456", "icon": "dog"},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["scope"] == "private"
    assert body["is_system"] is False
    assert body["icon"] == "dog"

    list_response = await client.get("/api/v1/categories", headers=auth_headers(token))
    names = [c["name"] for c in list_response.json()]
    assert "Pets" in names
    assert len(list_response.json()) == 8


async def test_creating_more_than_three_private_categories_is_allowed(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Limite de 3 categorias privadas (PRD §6.3) removido em 2026-09-09 — sem teto."""
    _, token = await make_user()

    for name in ("Pets", "Assinaturas", "Viagem", "Quarta"):
        response = await client.post(
            "/api/v1/categories",
            headers=auth_headers(token),
            json={"name": name, "color": "#123456", "icon": "tag"},
        )
        assert response.status_code == 201


async def test_duplicate_private_category_name_is_rejected_case_insensitively(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()

    first = await client.post(
        "/api/v1/categories",
        headers=auth_headers(token),
        json={"name": "Mercado", "color": "#123456", "icon": "shopping-bag"},
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/categories",
        headers=auth_headers(token),
        json={"name": "mercado", "color": "#654321", "icon": "shopping-bag"},
    )
    assert duplicate.status_code == 422


async def test_global_category_cannot_be_edited_or_deleted_by_common_user(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """RN-02: categorias globais são visíveis a todos, mas só leitura para usuário comum."""
    _, token = await make_user()

    listing = await client.get("/api/v1/categories", headers=auth_headers(token))
    global_category = next(c for c in listing.json() if c["scope"] == "global")

    update_response = await client.patch(
        f"/api/v1/categories/{global_category['public_id']}",
        headers=auth_headers(token),
        json={"name": "Hacked"},
    )
    assert update_response.status_code == 403

    delete_response = await client.delete(
        f"/api/v1/categories/{global_category['public_id']}", headers=auth_headers(token)
    )
    assert delete_response.status_code == 403


async def test_user_cannot_edit_or_delete_another_users_private_category(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """RN-01: isolamento por user_id — categoria privada de outro usuário retorna 404, não 403 (não revela existência)."""
    _, token_owner = await make_user()
    _, token_intruder = await make_user()

    create_response = await client.post(
        "/api/v1/categories",
        headers=auth_headers(token_owner),
        json={"name": "SóDoDono", "color": "#123456", "icon": "tag"},
    )
    public_id = create_response.json()["public_id"]

    update_response = await client.patch(
        f"/api/v1/categories/{public_id}",
        headers=auth_headers(token_intruder),
        json={"name": "Roubado"},
    )
    assert update_response.status_code == 404

    delete_response = await client.delete(
        f"/api/v1/categories/{public_id}", headers=auth_headers(token_intruder)
    )
    assert delete_response.status_code == 404


async def test_owner_can_update_and_delete_own_private_category(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()

    create_response = await client.post(
        "/api/v1/categories",
        headers=auth_headers(token),
        json={"name": "Original", "color": "#123456", "icon": "tag"},
    )
    public_id = create_response.json()["public_id"]

    update_response = await client.patch(
        f"/api/v1/categories/{public_id}",
        headers=auth_headers(token),
        json={"name": "Renomeada", "color": "#abcdef", "icon": "gift"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renomeada"
    assert update_response.json()["icon"] == "gift"

    delete_response = await client.delete(f"/api/v1/categories/{public_id}", headers=auth_headers(token))
    assert delete_response.status_code == 204

    listing = await client.get("/api/v1/categories", headers=auth_headers(token))
    assert all(c["public_id"] != public_id for c in listing.json())


async def test_malformed_public_id_returns_not_found_instead_of_error(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()

    response = await client.patch(
        "/api/v1/categories/not-a-valid-ulid", headers=auth_headers(token), json={"name": "x"}
    )
    assert response.status_code == 404


async def test_deleting_user_cascades_private_categories(
    db_session: AsyncSession, make_user: Callable[..., Any]
) -> None:
    """RN-03 (Observações do build-context-02): ON DELETE CASCADE em categories.user_id."""
    user, _ = await make_user()

    category = CategoryModel(public_id="01ARZ3NDEKTSV4RRFFQ69G5FAV", name="Vai Sumir", color="#123456", user_id=user.id)
    db_session.add(category)
    await db_session.flush()

    await db_session.execute(delete(UserModel).where(UserModel.id == user.id))
    await db_session.flush()

    remaining = await db_session.execute(
        select(CategoryModel).where(CategoryModel.user_id == user.id)
    )
    assert remaining.scalar_one_or_none() is None
