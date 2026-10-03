from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.transaction.use_cases.generate_due_recurrences import (
    GenerateDueRecurrencesUseCase,
)
from src.infrastructure.database.repositories.recurrence_rule_repository import (
    SqlAlchemyRecurrenceRuleRepository,
)
from src.infrastructure.database.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _global_category_id(client: AsyncClient, token: str) -> str:
    """Categoria de sistema (global) usada como categoria padrão nos testes."""
    listing = await client.get("/api/v1/categories", headers=auth_headers(token))
    return next(c for c in listing.json() if c["scope"] == "global")["public_id"]


async def _create_transaction(
    client: AsyncClient,
    token: str,
    category_id: str,
    *,
    amount: str = "50.00",
    description: str = "Mercado",
    date_str: str = "2026-08-05",
    status: str | None = None,
    payment_method: str | None = None,
    installment: dict | None = None,
    recurrence: dict | None = None,
) -> dict:
    """Toda transação criada pela API é despesa — produto é expense-only (2026-08-14)."""
    payload: dict[str, Any] = {
        "category_id": category_id,
        "amount": amount,
        "description": description,
        "date": date_str,
    }
    if status is not None:
        payload["status"] = status
    if payment_method is not None:
        payload["payment_method"] = payment_method
    if installment is not None:
        payload["installment"] = installment
    if recurrence is not None:
        payload["recurrence"] = recurrence
    response = await client.post("/api/v1/transactions", headers=auth_headers(token), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_transaction_with_global_category(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)

    body = await _create_transaction(client, token, category_id)

    assert body["category"]["public_id"] == category_id
    assert body["amount"] == "50.00"
    assert body["status"] == "paid"
    assert body["is_recurring"] is False
    assert body["installment"] is None


async def test_create_transaction_with_negative_amount_is_rejected(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)

    response = await client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        json={
            "category_id": category_id,
            "amount": "-10.00",
            "description": "x",
            "date": "2026-08-05",
        },
    )
    assert response.status_code == 422


async def test_create_transaction_with_installment_and_recurrence_together_is_rejected(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Parcelamento e recorrência são mecanismos mutuamente exclusivos (build-context-03 §2.7)."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)

    response = await client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        json={
            "category_id": category_id,
            "amount": "10.00",
            "description": "x",
            "date": "2026-08-05",
            "installment": {"total": 2},
            "recurrence": {"frequency": "monthly"},
        },
    )
    assert response.status_code == 422


async def test_create_transaction_with_another_users_private_category_is_rejected(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """RN-01: categoria privada de outro usuário retorna 404 na criação, não 403."""
    _, owner_token = await make_user()
    _, intruder_token = await make_user()
    private_category = await client.post(
        "/api/v1/categories",
        headers=auth_headers(owner_token),
        json={"name": "SóDoDono", "color": "#123456", "icon": "tag"},
    )
    category_id = private_category.json()["public_id"]

    response = await client.post(
        "/api/v1/transactions",
        headers=auth_headers(intruder_token),
        json={
            "category_id": category_id,
            "amount": "10.00",
            "description": "x",
            "date": "2026-08-05",
        },
    )
    assert response.status_code == 404


async def test_get_update_delete_return_404_for_another_users_transaction(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """RN-01: isolamento por user_id em GET/PUT/DELETE."""
    _, owner_token = await make_user()
    _, intruder_token = await make_user()
    category_id = await _global_category_id(client, owner_token)
    transaction = await _create_transaction(client, owner_token, category_id)
    public_id = transaction["public_id"]

    get_response = await client.get(
        f"/api/v1/transactions/{public_id}", headers=auth_headers(intruder_token)
    )
    assert get_response.status_code == 404

    put_response = await client.put(
        f"/api/v1/transactions/{public_id}",
        headers=auth_headers(intruder_token),
        json={"description": "Hacked"},
    )
    assert put_response.status_code == 404

    delete_response = await client.delete(
        f"/api/v1/transactions/{public_id}", headers=auth_headers(intruder_token)
    )
    assert delete_response.status_code == 404


async def test_month_filter_without_year_is_rejected(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()
    response = await client.get("/api/v1/transactions?month=8", headers=auth_headers(token))
    assert response.status_code == 422


async def test_filter_by_year_and_month(client: AsyncClient, make_user: Callable[..., Any]) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    await _create_transaction(client, token, category_id, date_str="2026-08-05", description="Agosto")
    await _create_transaction(
        client, token, category_id, date_str="2026-09-05", description="Setembro"
    )

    response = await client.get("/api/v1/transactions?year=2026&month=8", headers=auth_headers(token))
    assert [item["description"] for item in response.json()["items"]] == ["Agosto"]


async def test_search_by_description_and_by_category_name(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """RN-05: description é criptografado — a busca precisa funcionar mesmo assim (em memória)."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    categories = (await client.get("/api/v1/categories", headers=auth_headers(token))).json()
    category_name = next(c for c in categories if c["public_id"] == category_id)["name"]

    await _create_transaction(client, token, category_id, description="Compra no mercado")
    await _create_transaction(client, token, category_id, description="Outra coisa qualquer")

    by_description = await client.get("/api/v1/transactions?q=mercado", headers=auth_headers(token))
    assert len(by_description.json()["items"]) == 1

    by_category = await client.get(
        f"/api/v1/transactions?q={category_name}", headers=auth_headers(token)
    )
    assert len(by_category.json()["items"]) == 2


async def test_search_matches_payment_method_by_raw_value_and_pt_br_label(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: A busca por texto passa a bater com o tipo de pagamento
    (pedido direto do usuário, fora de qualquer build-context) — tanto
    pelo valor bruto salvo (`pix`) quanto pelo rótulo em português que
    o usuário vê na tela (`cartão` → `credit_card`).
    """
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    await _create_transaction(client, token, category_id, description="A", payment_method="pix")
    await _create_transaction(
        client, token, category_id, description="B", payment_method="credit_card"
    )
    await _create_transaction(client, token, category_id, description="C", payment_method=None)

    by_raw_value = await client.get("/api/v1/transactions?q=pix", headers=auth_headers(token))
    assert [item["description"] for item in by_raw_value.json()["items"]] == ["A"]

    by_pt_br_label = await client.get(
        "/api/v1/transactions?q=cart%C3%A3o", headers=auth_headers(token)
    )
    assert [item["description"] for item in by_pt_br_label.json()["items"]] == ["B"]


async def test_pagination_and_summary_reflect_full_filtered_set(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """summary deve refletir o conjunto filtrado inteiro, não só a página atual."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    for index in range(5):
        await _create_transaction(client, token, category_id, amount="10.00", description=f"Item {index}")

    response = await client.get("/api/v1/transactions?page=1&page_size=2", headers=auth_headers(token))
    body = response.json()
    assert len(body["items"]) == 2
    assert body["pagination"]["total"] == 5
    assert body["pagination"]["total_pages"] == 3
    assert body["summary"]["count"] == 5
    assert body["summary"]["total_amount"] == "50.00"


async def test_update_transaction_partial(client: AsyncClient, make_user: Callable[..., Any]) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    transaction = await _create_transaction(client, token, category_id, description="Original")

    response = await client.put(
        f"/api/v1/transactions/{transaction['public_id']}",
        headers=auth_headers(token),
        json={"description": "Atualizada", "status": "paid"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "Atualizada"
    assert body["status"] == "paid"
    assert body["amount"] == transaction["amount"]


async def test_mark_pending_transaction_as_paid_sets_status_and_paid_at(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    transaction = await _create_transaction(client, token, category_id, status="pending")
    assert transaction["status"] == "pending"
    assert transaction["paid_at"] is None

    response = await client.put(
        f"/api/v1/transactions/{transaction['public_id']}",
        headers=auth_headers(token),
        json={"status": "paid", "paid_at": "2026-08-12"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "paid"
    assert body["paid_at"] == "2026-08-12"

    get_response = await client.get(
        f"/api/v1/transactions/{transaction['public_id']}", headers=auth_headers(token)
    )
    assert get_response.json()["paid_at"] == "2026-08-12"


async def test_delete_transaction(client: AsyncClient, make_user: Callable[..., Any]) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    transaction = await _create_transaction(client, token, category_id)

    response = await client.delete(
        f"/api/v1/transactions/{transaction['public_id']}", headers=auth_headers(token)
    )
    assert response.status_code == 204

    get_response = await client.get(
        f"/api/v1/transactions/{transaction['public_id']}", headers=auth_headers(token)
    )
    assert get_response.status_code == 404


async def test_bulk_delete_is_idempotent(client: AsyncClient, make_user: Callable[..., Any]) -> None:
    """Ids inexistentes/malformados/de outro usuário são ignorados, mas contam em requested_count."""
    _, owner_token = await make_user()
    _, intruder_token = await make_user()
    category_id = await _global_category_id(client, owner_token)
    tx1 = await _create_transaction(client, owner_token, category_id)
    tx2 = await _create_transaction(client, owner_token, category_id)

    other_category_id = await _global_category_id(client, intruder_token)
    other_tx = await _create_transaction(client, intruder_token, other_category_id)

    response = await client.post(
        "/api/v1/transactions/bulk-delete",
        headers=auth_headers(owner_token),
        json={
            "public_ids": [
                tx1["public_id"],
                tx2["public_id"],
                other_tx["public_id"],
                "not-a-valid-ulid",
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["deleted_count"] == 2
    assert body["requested_count"] == 4


async def test_installment_generates_all_occurrences_with_same_group(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    first = await _create_transaction(
        client,
        token,
        category_id,
        amount="150.00",
        description="Notebook",
        installment={"total": 3},
    )
    assert first["installment"] == {
        "group_id": first["installment"]["group_id"],
        "number": 1,
        "total": 3,
    }
    group_id = first["installment"]["group_id"]

    response = await client.get("/api/v1/transactions?page_size=50", headers=auth_headers(token))
    installments = [
        item
        for item in response.json()["items"]
        if item["installment"] and item["installment"]["group_id"] == group_id
    ]
    assert len(installments) == 3
    assert sorted(item["installment"]["number"] for item in installments) == [1, 2, 3]
    assert all(item["amount"] == "150.00" for item in installments)


async def test_delete_all_occurrences_removes_every_installment_of_the_group(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """`?all_occurrences=true` numa parcela exclui as 3 parcelas do grupo, sem afetar outra compra."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    first = await _create_transaction(
        client,
        token,
        category_id,
        description="Notebook",
        installment={"total": 3},
    )
    other = await _create_transaction(client, token, category_id, description="Mercado avulso")

    response = await client.delete(
        f"/api/v1/transactions/{first['public_id']}?all_occurrences=true",
        headers=auth_headers(token),
    )
    assert response.status_code == 204

    listing = await client.get("/api/v1/transactions?page_size=50", headers=auth_headers(token))
    remaining_ids = {item["public_id"] for item in listing.json()["items"]}
    assert remaining_ids == {other["public_id"]}


async def test_delete_all_occurrences_on_plain_transaction_deletes_only_it(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Transação avulsa (sem recorrência nem parcelamento) ignora o flag e exclui só ela mesma."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    transaction = await _create_transaction(client, token, category_id)

    response = await client.delete(
        f"/api/v1/transactions/{transaction['public_id']}?all_occurrences=true",
        headers=auth_headers(token),
    )
    assert response.status_code == 204

    get_response = await client.get(
        f"/api/v1/transactions/{transaction['public_id']}", headers=auth_headers(token)
    )
    assert get_response.status_code == 404


async def test_only_first_installment_can_be_paid_rest_are_always_pending(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Ajuste de 2026-08-09: status "pago" no formulário só se aplica à 1ª
    parcela — as demais nascem pendentes mesmo pedindo status="paid"."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    first = await _create_transaction(
        client,
        token,
        category_id,
        amount="99.00",
        description="TV parcelada",
        status="paid",
        installment={"total": 4},
    )
    assert first["installment"]["number"] == 1
    assert first["status"] == "paid"
    group_id = first["installment"]["group_id"]

    response = await client.get("/api/v1/transactions?page_size=50", headers=auth_headers(token))
    installments = {
        item["installment"]["number"]: item
        for item in response.json()["items"]
        if item["installment"] and item["installment"]["group_id"] == group_id
    }
    assert installments[1]["status"] == "paid"
    assert installments[2]["status"] == "pending"
    assert installments[3]["status"] == "pending"
    assert installments[4]["status"] == "pending"


async def test_recurring_transaction_materializes_first_occurrence_and_next_via_job(
    client: AsyncClient, make_user: Callable[..., Any], db_session: AsyncSession
) -> None:
    """Recorrência não pré-gera nada — só a 1ª ocorrência (síncrona) + o que o job materializar."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    created = await _create_transaction(
        client,
        token,
        category_id,
        amount="19.90",
        description="Spotify",
        date_str="2026-07-01",
        status="paid",
        recurrence={"frequency": "monthly"},
    )
    assert created["is_recurring"] is True
    assert created["status"] == "paid"

    recurrences = await client.get("/api/v1/transactions/recurrences", headers=auth_headers(token))
    rule = recurrences.json()[0]
    assert rule["next_occurrence_date"] == "2026-08-01"

    use_case = GenerateDueRecurrencesUseCase(
        transaction_repository=SqlAlchemyTransactionRepository(db_session),
        recurrence_rule_repository=SqlAlchemyRecurrenceRuleRepository(db_session),
    )
    generated = await use_case.execute(date(2026, 8, 9))
    assert generated == 1

    listing = await client.get(
        "/api/v1/transactions?q=Spotify&year=2026&page_size=50", headers=auth_headers(token)
    )
    items = {item["date"]: item for item in listing.json()["items"]}
    assert sorted(items) == ["2026-07-01", "2026-08-01"]
    # Ajuste de 2026-08-09: só a 1ª ocorrência (materializada na criação)
    # herda o status escolhido pelo usuário — a que o job gera depois
    # nasce sempre pendente, nunca "paga" sem confirmação.
    assert items["2026-07-01"]["status"] == "paid"
    assert items["2026-08-01"]["status"] == "pending"


async def test_cancel_recurrence_stops_future_generation(
    client: AsyncClient, make_user: Callable[..., Any], db_session: AsyncSession
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    await _create_transaction(
        client,
        token,
        category_id,
        amount="9.90",
        description="Assinatura",
        date_str="2026-07-01",
        recurrence={"frequency": "monthly"},
    )
    recurrences = await client.get("/api/v1/transactions/recurrences", headers=auth_headers(token))
    rule_public_id = recurrences.json()[0]["public_id"]

    cancel_response = await client.delete(
        f"/api/v1/transactions/recurrences/{rule_public_id}", headers=auth_headers(token)
    )
    assert cancel_response.status_code == 204

    after_cancel = await client.get(
        "/api/v1/transactions/recurrences", headers=auth_headers(token)
    )
    assert after_cancel.json() == []

    use_case = GenerateDueRecurrencesUseCase(
        transaction_repository=SqlAlchemyTransactionRepository(db_session),
        recurrence_rule_repository=SqlAlchemyRecurrenceRuleRepository(db_session),
    )
    generated = await use_case.execute(date(2026, 8, 9))
    assert generated == 0


async def test_budget_default_is_null_and_reflects_in_summary_once_set(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    _, token = await make_user()
    initial = await client.get("/api/v1/transactions/budget", headers=auth_headers(token))
    assert initial.json()["monthly_budget"] is None

    updated = await client.put(
        "/api/v1/transactions/budget",
        headers=auth_headers(token),
        json={"monthly_budget": "1000.00"},
    )
    assert updated.json()["monthly_budget"] == "1000.00"

    category_id = await _global_category_id(client, token)
    await _create_transaction(client, token, category_id, amount="250.00", date_str="2026-08-05")

    listing = await client.get("/api/v1/transactions?year=2026&month=8", headers=auth_headers(token))
    summary = listing.json()["summary"]
    assert summary["budget_limit"] == "1000.00"
    assert summary["budget_used_percentage"] == 25.0

    # Período de ano inteiro não tem "um mês" para comparar — teto some do summary.
    yearly = await client.get("/api/v1/transactions?year=2026", headers=auth_headers(token))
    assert yearly.json()["summary"]["budget_limit"] is None


async def test_upload_and_delete_receipt(
    client: AsyncClient, make_user: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backblaze real não está configurado no ambiente de teste — o client é substituído por um fake."""
    uploaded: dict[str, Any] = {}

    class FakeStorageClient:
        def upload(self, key: str, content: bytes, content_type: str) -> None:
            uploaded["key"] = key
            uploaded["content_type"] = content_type

        def delete(self, key: str) -> None:
            uploaded.pop("key", None)

        def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
            return f"https://fake-b2.example.com/{key}"

    monkeypatch.setattr(
        "src.presentation.api.v1.transactions.router.BackblazeStorageClient", FakeStorageClient
    )

    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    transaction = await _create_transaction(client, token, category_id)

    upload_response = await client.post(
        f"/api/v1/transactions/{transaction['public_id']}/receipt",
        headers=auth_headers(token),
        files={"file": ("nota.png", b"fake-image-bytes", "image/png")},
    )
    assert upload_response.status_code == 200
    body = upload_response.json()
    assert body["receipt_url"] is not None
    assert "key" in uploaded

    delete_response = await client.delete(
        f"/api/v1/transactions/{transaction['public_id']}/receipt", headers=auth_headers(token)
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["receipt_url"] is None
    assert "key" not in uploaded


async def test_upload_receipt_rejects_unsupported_content_type(
    client: AsyncClient, make_user: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeStorageClient:
        def upload(self, *args: Any, **kwargs: Any) -> None:
            raise AssertionError("should not be called for an invalid file")

        def delete(self, *args: Any, **kwargs: Any) -> None:
            raise AssertionError("should not be called for an invalid file")

        def generate_presigned_url(self, *args: Any, **kwargs: Any) -> str:
            return "unused"

    monkeypatch.setattr(
        "src.presentation.api.v1.transactions.router.BackblazeStorageClient", FakeStorageClient
    )

    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    transaction = await _create_transaction(client, token, category_id)

    response = await client.post(
        f"/api/v1/transactions/{transaction['public_id']}/receipt",
        headers=auth_headers(token),
        files={"file": ("nota.exe", b"binary", "application/x-msdownload")},
    )
    assert response.status_code == 422


async def test_deleting_category_in_use_returns_409(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """FK ON DELETE RESTRICT (build-context-03) — categoria com transações não pode ser excluída."""
    _, token = await make_user()
    private_category = await client.post(
        "/api/v1/categories",
        headers=auth_headers(token),
        json={"name": "EmUso", "color": "#123456", "icon": "tag"},
    )
    category_id = private_category.json()["public_id"]
    await _create_transaction(client, token, category_id)

    response = await client.delete(f"/api/v1/categories/{category_id}", headers=auth_headers(token))
    assert response.status_code == 409
