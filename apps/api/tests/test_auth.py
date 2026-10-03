from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import FakeArqPool, auth_headers

pytestmark = pytest.mark.asyncio


async def test_linking_a_new_phone_enqueues_whatsapp_welcome_message(
    client: AsyncClient, make_user: Callable[..., Any], fake_arq_pool: FakeArqPool
) -> None:
    """Perfil sem telefone → salvar um número pela 1ª vez enfileira a boas-vindas."""
    user, token = await make_user()
    assert user.phone is None

    response = await client.patch(
        "/api/v1/auth/me", json={"phone": "+55 11 99999-0001"}, headers=auth_headers(token)
    )

    assert response.status_code == 200
    welcome_calls = [
        call for call in fake_arq_pool.enqueued if call[0] == "send_whatsapp_welcome_message"
    ]
    assert welcome_calls == [("send_whatsapp_welcome_message", (str(user.id),))]


async def test_changing_phone_to_a_different_number_enqueues_again(
    client: AsyncClient, make_user: Callable[..., Any], fake_arq_pool: FakeArqPool
) -> None:
    """Trocar um número já vinculado por outro diferente também enfileira."""
    user, token = await make_user()
    await client.patch(
        "/api/v1/auth/me", json={"phone": "+55 11 99999-0002"}, headers=auth_headers(token)
    )
    fake_arq_pool.enqueued.clear()

    response = await client.patch(
        "/api/v1/auth/me", json={"phone": "+55 11 99999-0003"}, headers=auth_headers(token)
    )

    assert response.status_code == 200
    welcome_calls = [
        call for call in fake_arq_pool.enqueued if call[0] == "send_whatsapp_welcome_message"
    ]
    assert welcome_calls == [("send_whatsapp_welcome_message", (str(user.id),))]


async def test_saving_the_same_phone_again_does_not_enqueue(
    client: AsyncClient, make_user: Callable[..., Any], fake_arq_pool: FakeArqPool
) -> None:
    """Salvar exatamente o mesmo número de novo não reenvia a mensagem de boas-vindas."""
    _, token = await make_user()
    await client.patch(
        "/api/v1/auth/me", json={"phone": "+55 11 99999-0004"}, headers=auth_headers(token)
    )
    fake_arq_pool.enqueued.clear()

    response = await client.patch(
        "/api/v1/auth/me", json={"phone": "+55 11 99999-0004"}, headers=auth_headers(token)
    )

    assert response.status_code == 200
    assert fake_arq_pool.enqueued == []


async def test_updating_name_without_touching_phone_does_not_enqueue(
    client: AsyncClient, make_user: Callable[..., Any], fake_arq_pool: FakeArqPool
) -> None:
    """Atualizar só o nome (sem enviar `phone`) não dispara a mensagem de boas-vindas."""
    _, token = await make_user()

    response = await client.patch(
        "/api/v1/auth/me", json={"name": "Novo Nome"}, headers=auth_headers(token)
    )

    assert response.status_code == 200
    assert fake_arq_pool.enqueued == []


@pytest.mark.parametrize(
    "invalid_phone",
    [
        "+55",  # só o DDI, sem DDD/assinante
        "+5511",  # DDI + DDD, sem assinante
        "+551199999",  # assinante truncado
        "11999990001",  # sem o `+`/DDI
        "not-a-phone",
    ],
)
async def test_saving_an_incomplete_or_invalid_phone_is_rejected(
    client: AsyncClient, make_user: Callable[..., Any], invalid_phone: str
) -> None:
    """`PATCH /auth/me` recusa (422) um `phone` sem DDI ou incompleto — RN de validação
    de 2026-08-19: o número precisa ser um E.164 válido (`phonenumbers.is_valid_number`),
    não só uma string não vazia."""
    _, token = await make_user()

    response = await client.patch(
        "/api/v1/auth/me", json={"phone": invalid_phone}, headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_saving_a_valid_phone_is_normalized_to_e164(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Um número válido com máscara/espaços é normalizado para E.164 puro antes de
    persistir — `+55 11 99999-0005` vira `+5511999990005`."""
    _, token = await make_user()

    response = await client.patch(
        "/api/v1/auth/me", json={"phone": "+55 11 99999-0005"}, headers=auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "+5511999990005"


async def test_saving_an_empty_phone_does_not_change_it(
    client: AsyncClient, make_user: Callable[..., Any], fake_arq_pool: FakeArqPool
) -> None:
    """`phone: ""` (enviado pelo Admin Profile, que não omite a chave quando o campo
    não é tocado) é tratado como "sem alteração", não como um número inválido."""
    user, token = await make_user()
    assert user.phone is None

    response = await client.patch(
        "/api/v1/auth/me", json={"name": user.name, "phone": ""}, headers=auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["phone"] is None
    assert fake_arq_pool.enqueued == []


async def test_new_user_starts_with_onboarding_not_completed(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()

    response = await client.get("/api/v1/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is False


async def test_marking_onboarding_completed_persists(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()

    response = await client.patch(
        "/api/v1/auth/me/onboarding", json={"onboarding_completed": True}, headers=auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is True

    check = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert check.json()["onboarding_completed"] is True


async def test_resetting_onboarding_persists_false_again(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """"Reiniciar tour" em Configurações — desmarca de volta pra false."""
    _, token = await make_user()
    await client.patch(
        "/api/v1/auth/me/onboarding", json={"onboarding_completed": True}, headers=auth_headers(token)
    )

    response = await client.patch(
        "/api/v1/auth/me/onboarding", json={"onboarding_completed": False}, headers=auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is False
