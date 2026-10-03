import uuid
from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.feedback import Feedback as FeedbackModel
from src.infrastructure.database.models.user import User as UserModel
from src.infrastructure.security.password_hasher import PasswordHasher
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _global_category_id(client: AsyncClient, token: str) -> str:
    listing = await client.get("/api/v1/categories", headers=auth_headers(token))
    return next(c for c in listing.json() if c["scope"] == "global")["public_id"]


async def test_non_admin_gets_403_on_admin_stats(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Usuário comum recebe 403 em qualquer rota /admin/* (RN-01, exceção documentada)."""
    _, token = await make_user(role="user")

    response = await client.get("/api/v1/admin/stats", headers=auth_headers(token))

    assert response.status_code == 403


async def test_admin_stats_returns_totals_and_six_month_series(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, admin_token = await make_user(role="admin")
    await make_user(role="user")

    response = await client.get("/api/v1/admin/stats", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert body["total_users"] >= 2
    assert len(body["new_users_by_month"]) == 6


async def test_list_users_paginated(client: AsyncClient, make_user: Callable[..., Any]) -> None:
    _, admin_token = await make_user(role="admin")
    await make_user(role="user")

    response = await client.get("/api/v1/admin/users", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert body["page"] == 1
    assert body["page_size"] == 20


async def test_list_users_filters_by_role(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, admin_token = await make_user(role="admin")

    response = await client.get(
        "/api/v1/admin/users", params={"role": "admin"}, headers=auth_headers(admin_token)
    )

    assert response.status_code == 200
    body = response.json()
    assert all(item["role"] == "admin" for item in body["items"])


async def test_get_user_detail(client: AsyncClient, make_user: Callable[..., Any]) -> None:
    target, admin_token = await make_user(role="admin")

    response = await client.get(
        f"/api/v1/admin/users/{target.id}", headers=auth_headers(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(target.id)


async def test_get_user_not_found_returns_404(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, admin_token = await make_user(role="admin")

    response = await client.get(
        f"/api/v1/admin/users/{uuid.uuid4()}", headers=auth_headers(admin_token)
    )

    assert response.status_code == 404


async def test_get_user_malformed_id_returns_404_not_422(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """UUID malformado é tratado como 404, nunca erro de validação (RN-01)."""
    _, admin_token = await make_user(role="admin")

    response = await client.get(
        "/api/v1/admin/users/not-a-uuid", headers=auth_headers(admin_token)
    )

    assert response.status_code == 404


async def test_change_user_role_promotes_to_admin(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    target, _ = await make_user(role="user")
    _, admin_token = await make_user(role="admin")

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        json={"role": "admin"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_grant_test_access_makes_effective_plan_premium(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Conceder acesso de teste vira `effective_plan=premium`
    na hora, mesmo a conta sendo Free por baixo — sem nenhuma interação
    com Stripe (fora de qualquer build-context, pedido direto do
    usuário).
    """
    target, _ = await make_user(role="user")
    _, admin_token = await make_user(role="admin")

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}/test-access",
        json={"enabled": True},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["effective_plan"] == "premium"
    assert body["is_admin_test_access"] is True


async def test_revoke_test_access_reverts_to_underlying_plan(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Revogar volta o `effective_plan` pro que a conta realmente tem por baixo (Free, no cadastro padrão)."""
    target, _ = await make_user(role="user")
    _, admin_token = await make_user(role="admin")
    await client.patch(
        f"/api/v1/admin/users/{target.id}/test-access",
        json={"enabled": True},
        headers=auth_headers(admin_token),
    )

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}/test-access",
        json={"enabled": False},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["effective_plan"] == "free"
    assert body["is_admin_test_access"] is False


async def test_list_users_includes_effective_plan_and_test_access_fields(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """A listagem também traz `effective_plan`/`is_admin_test_access` (resolvidos em lote, sem N+1)."""
    _, admin_token = await make_user(role="admin")

    response = await client.get("/api/v1/admin/users", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert all("effective_plan" in item and "is_admin_test_access" in item for item in body["items"])


async def test_admin_deletes_user_account(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """DELETE /admin/users/{id} remove a conta permanentemente (RN-03, cascade via FK)."""
    target, _ = await make_user(role="user")
    _, admin_token = await make_user(role="admin")

    response = await client.delete(
        f"/api/v1/admin/users/{target.id}", headers=auth_headers(admin_token)
    )

    assert response.status_code == 204

    follow_up = await client.get(
        f"/api/v1/admin/users/{target.id}", headers=auth_headers(admin_token)
    )
    assert follow_up.status_code == 404


async def test_delete_user_not_found_returns_404(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, admin_token = await make_user(role="admin")

    response = await client.delete(
        f"/api/v1/admin/users/{uuid.uuid4()}", headers=auth_headers(admin_token)
    )

    assert response.status_code == 404


async def test_admin_cannot_delete_own_account(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    admin, admin_token = await make_user(role="admin")

    response = await client.delete(
        f"/api/v1/admin/users/{admin.id}", headers=auth_headers(admin_token)
    )

    assert response.status_code == 400


async def test_non_admin_gets_403_on_delete_user(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    target, _ = await make_user(role="user")
    _, user_token = await make_user(role="user")

    response = await client.delete(
        f"/api/v1/admin/users/{target.id}", headers=auth_headers(user_token)
    )

    assert response.status_code == 403


async def test_non_admin_gets_403_on_test_access(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    target, _ = await make_user(role="user")
    _, user_token = await make_user(role="user")

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}/test-access",
        json={"enabled": True},
        headers=auth_headers(user_token),
    )

    assert response.status_code == 403


async def test_list_feedback_returns_hydrated_user_summary(
    client: AsyncClient, make_user: Callable[..., Any], db_session: AsyncSession
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Não assume tabela vazia — o banco de dev não é isolado
    entre a aplicação e os testes (sem banco de teste separado, ver
    `techContext.md`), então feedback real já pode existir. A asserção
    busca o item criado por mensagem única do teste, em vez de assumir
    `total == 1`.
    """
    target, admin_token = await make_user(role="admin")
    feedback = FeedbackModel(
        user_id=target.id,
        message=f"Adorei o app! {target.id}",
        channel="web",
    )
    db_session.add(feedback)
    await db_session.flush()

    response = await client.get(
        "/api/v1/admin/feedback", params={"page_size": 100}, headers=auth_headers(admin_token)
    )

    assert response.status_code == 200
    body = response.json()
    matches = [item for item in body["items"] if item["message"] == f"Adorei o app! {target.id}"]
    assert len(matches) == 1
    assert matches[0]["channel"] == "web"
    assert matches[0]["user"]["id"] == str(target.id)


async def test_list_feedback_filters_by_channel(
    client: AsyncClient, make_user: Callable[..., Any], db_session: AsyncSession
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Não assume tabela vazia (mesmo motivo do teste acima) —
    confirma que o filtro exclui o item de canal `web` e inclui o de
    `whatsapp`, em vez de assumir `total == 1`.
    """
    target, admin_token = await make_user(role="admin")
    web_message = f"Feedback web {target.id}"
    bot_message = f"Feedback bot {target.id}"
    db_session.add_all(
        [
            FeedbackModel(user_id=target.id, message=web_message, channel="web"),
            FeedbackModel(user_id=target.id, message=bot_message, channel="whatsapp"),
        ]
    )
    await db_session.flush()

    response = await client.get(
        "/api/v1/admin/feedback",
        params={"channel": "whatsapp", "page_size": 100},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    messages = [item["message"] for item in body["items"]]
    assert bot_message in messages
    assert web_message not in messages
    assert all(item["channel"] == "whatsapp" for item in body["items"])


async def _make_user_with_password(
    db_session: AsyncSession, *, role: str, password: str, email: str
) -> UserModel:
    model = UserModel(
        id=uuid.uuid4(),
        name="Login Test User",
        email=email,
        password_hash=PasswordHasher().hash(password),
        role=role,
        language="pt-BR",
    )
    db_session.add(model)
    await db_session.flush()
    return model


async def test_admin_login_succeeds_for_admin_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "super-secret-123"
    user = await _make_user_with_password(
        db_session, role="admin", password=password, email="admin-login-ok@example.com"
    )

    response = await client.post(
        "/api/v1/admin/auth/login", json={"email": user.email, "password": password}
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    assert "refresh_token" in response.cookies


async def test_admin_login_rejects_valid_credentials_without_admin_role(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Conta existe e a senha confere, mas role=user — resposta idêntica a credenciais inválidas."""
    password = "super-secret-123"
    user = await _make_user_with_password(
        db_session, role="user", password=password, email="user-login-rejected@example.com"
    )

    response = await client.post(
        "/api/v1/admin/auth/login", json={"email": user.email, "password": password}
    )

    assert response.status_code == 401
    assert "refresh_token" not in response.cookies


async def test_admin_login_rejects_wrong_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _make_user_with_password(
        db_session, role="admin", password="correct-password", email="admin-login-bad-pw@example.com"
    )

    response = await client.post(
        "/api/v1/admin/auth/login", json={"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == 401


async def test_admin_stats_includes_build_context_11_fields(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: build-context-11 §2.1 — só confirma a forma dos campos
    novos (banco de dev compartilhado entre testes, sem isolamento —
    ver `techContext.md` — então não dá pra assumir valor exato).
    """
    _, admin_token = await make_user(role="admin")

    response = await client.get("/api/v1/admin/stats", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["active_users_daily"], int)
    assert isinstance(body["active_users_monthly"], int)
    assert body["active_users_monthly"] >= body["active_users_daily"]
    distribution = body["subscriptions_by_plan"]
    assert {"free", "pro", "premium", "trial_pro"} <= distribution.keys()
    assert isinstance(body["mrr_cents"], int)
    assert isinstance(body["churn_rate"], (int, float))
    assert {"web", "whatsapp"} <= body["usage_by_channel"].keys()


async def test_admin_stats_dau_counts_user_with_fresh_transaction(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Cria uma transação agora mesmo pra um usuário novo — DAU precisa contar pelo menos +1 depois disso."""
    _, admin_token = await make_user(role="admin")
    before = await client.get("/api/v1/admin/stats", headers=auth_headers(admin_token))
    dau_before = before.json()["active_users_daily"]

    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    response = await client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        json={
            "category_id": category_id,
            "amount": "42.00",
            "description": "Ativo pra DAU",
            "date": "2026-09-11",
        },
    )
    assert response.status_code == 201, response.text

    after = await client.get("/api/v1/admin/stats", headers=auth_headers(admin_token))
    dau_after = after.json()["active_users_daily"]

    assert dau_after >= dau_before + 1


async def test_non_admin_gets_403_on_admin_activity(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user(role="user")

    response = await client.get("/api/v1/admin/activity", headers=auth_headers(token))

    assert response.status_code == 403


async def test_admin_activity_lists_new_registration(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """RegisterUserUseCase grava `user_registered` no feed (build-context-11 §2.3)."""
    _, admin_token = await make_user(role="admin")
    name = f"Activity Test User {uuid.uuid4().hex[:8]}"
    await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": f"{uuid.uuid4().hex[:12]}@example.com", "password": "Sup3rSecret!"},
    )

    response = await client.get(
        "/api/v1/admin/activity", params={"page_size": 100}, headers=auth_headers(admin_token)
    )

    assert response.status_code == 200
    body = response.json()
    matches = [item for item in body["items"] if item["message"] == f"{name} se cadastrou"]
    assert len(matches) == 1
    assert matches[0]["event_type"] == "user_registered"


async def test_non_admin_gets_403_on_admin_payments(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user(role="user")

    response = await client.get("/api/v1/admin/payments", headers=auth_headers(token))

    assert response.status_code == 403


async def test_admin_payments_returns_financial_kpis(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, admin_token = await make_user(role="admin")

    response = await client.get("/api/v1/admin/payments", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["mrr_cents"], int)
    assert body["arr_cents"] == body["mrr_cents"] * 12
    assert isinstance(body["churn_rate"], (int, float))
    assert isinstance(body["average_ticket_cents"], int)
    assert isinstance(body["past_due_count"], int)
    assert isinstance(body["recent_payments"], list)
    assert isinstance(body["recent_stripe_events"], list)
