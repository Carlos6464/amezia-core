from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reports.use_cases.generate_ai_narrative import (
    GenerateAiNarrativeInput,
    GenerateAiNarrativeUseCase,
)
from src.domain.conversation.ports import ChatCompletionResult
from src.domain.conversation.value_objects import AiProvider
from src.domain.reports.value_objects import PeriodRange
from src.domain.transaction.value_objects import Period
from src.domain.user.value_objects import Language
from src.infrastructure.database.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_reports_repository import (
    SqlAlchemyReportsRepository,
)
from src.infrastructure.security.jwt_service import JwtService
from tests.conftest import FakeArqPool, auth_headers

pytestmark = pytest.mark.asyncio


class _FakeChatCompletionPort:
    """Mesmo padrão de `test_conversations.py::_FakeChatCompletionPort`."""

    def __init__(self, response: str = "Narrativa gerada.") -> None:
        self.response = response
        self.calls = 0
        self.received_system_instruction: str | None = None

    async def complete(self, system_instruction: str, messages: list) -> ChatCompletionResult:
        self.calls += 1
        self.received_system_instruction = system_instruction
        return ChatCompletionResult(
            content=self.response,
            provider=AiProvider.GEMINI,
            model="gemini-2.5-flash",
            input_tokens=10,
            output_tokens=5,
        )


class _FakeCheckAiUsageLimitUseCase:
    """Nunca bloqueia — o limite de plano é coberto à parte em test_subscriptions.py."""

    async def execute(self, input_data: object) -> None:
        return None


class _FakeRecordAiUsageUseCase:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def execute(self, input_data: object) -> None:
        self.calls.append(input_data)


async def _global_category_id(client: AsyncClient, token: str) -> str:
    listing = await client.get("/api/v1/categories", headers=auth_headers(token))
    return next(c for c in listing.json() if c["scope"] == "global")["public_id"]


async def _create_private_category(client: AsyncClient, token: str, name: str) -> str:
    response = await client.post(
        "/api/v1/categories",
        headers=auth_headers(token),
        json={"name": name, "color": "#6366f1", "icon": "tag"},
    )
    assert response.status_code == 201, response.text
    return response.json()["public_id"]


async def _create_transaction(
    client: AsyncClient,
    token: str,
    category_id: str,
    *,
    amount: str = "50.00",
    description: str = "Mercado",
    date_str: str = "2026-06-05",
    status: str | None = None,
    payment_method: str | None = None,
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
    response = await client.post(
        "/api/v1/transactions", headers=auth_headers(token), json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_transaction_is_always_expense(client: AsyncClient, make_user: Any) -> None:
    """Payload não aceita mais `type` — toda transação criada é despesa."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)

    body = await _create_transaction(client, token, category_id)

    assert body["type"] == "expense"


async def test_financial_summary_totals_and_top_category(
    client: AsyncClient, make_user: Any
) -> None:
    """Total, contagem, maior categoria e maior transação do período."""
    _, token = await make_user()
    category_id = await _global_category_id(client, token)

    await _create_transaction(client, token, category_id, amount="60.00", description="Padaria")
    await _create_transaction(client, token, category_id, amount="40.00", description="Mercado")

    response = await client.get(
        "/api/v1/reports/summary",
        headers=auth_headers(token),
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_expense"] == "100.00"
    assert body["transaction_count"] == 2
    assert body["top_category"]["total"] == "100.00"
    assert body["biggest_transaction"]["amount"] == "60.00"
    assert body["biggest_transaction"]["description"] == "Padaria"
    assert "total_income" not in body
    assert "balance" not in body


async def test_financial_summary_isolated_by_user(client: AsyncClient, make_user: Any) -> None:
    """RN-01: transações de outro usuário nunca entram no resumo."""
    _, token_a = await make_user()
    _, token_b = await make_user()
    category_a = await _global_category_id(client, token_a)
    category_b = await _global_category_id(client, token_b)

    await _create_transaction(client, token_a, category_a, amount="100.00")
    await _create_transaction(client, token_b, category_b, amount="999.00")

    response = await client.get(
        "/api/v1/reports/summary",
        headers=auth_headers(token_a),
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )

    assert response.status_code == 200
    assert response.json()["total_expense"] == "100.00"


async def test_monthly_evolution_returns_requested_number_of_points(
    client: AsyncClient, make_user: Any
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    await _create_transaction(client, token, category_id, amount="25.00", date_str="2026-06-10")

    response = await client.get(
        "/api/v1/reports/monthly-evolution",
        headers=auth_headers(token),
        params={"year": 2026, "month": 6, "months": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert body[-1]["year"] == 2026
    assert body[-1]["month"] == 6
    assert body[-1]["total_expense"] == "25.00"
    assert body[0]["month"] == 4


async def test_category_distribution_ordered_by_total_desc(
    client: AsyncClient, make_user: Any
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    other_category_id = await _create_private_category(client, token, "Transporte")

    await _create_transaction(client, token, category_id, amount="20.00")
    await _create_transaction(client, token, other_category_id, amount="80.00")

    response = await client.get(
        "/api/v1/reports/category-distribution",
        headers=auth_headers(token),
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["category_id"] == other_category_id
    assert body[0]["total"] == "80.00"
    assert body[0]["percentage"] == pytest.approx(80.0)


async def test_payment_method_distribution_groups_not_informed_separately(
    client: AsyncClient, make_user: Any
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Distribuição por tipo de pagamento (pedido direto do
    usuário, fora de qualquer build-context) — agrupa por
    `payment_method`, e transação sem esse campo preenchido entra numa
    fatia própria (`not_informed`) em vez de sumir da soma.
    """
    _, token = await make_user()
    category_id = await _global_category_id(client, token)

    await _create_transaction(
        client, token, category_id, amount="70.00", payment_method="pix"
    )
    await _create_transaction(
        client, token, category_id, amount="20.00", payment_method="credit_card"
    )
    await _create_transaction(client, token, category_id, amount="10.00")

    response = await client.get(
        "/api/v1/reports/payment-method-distribution",
        headers=auth_headers(token),
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )

    assert response.status_code == 200
    body = response.json()
    by_method = {item["payment_method"]: item for item in body}
    assert by_method["pix"]["total"] == "70.00"
    assert by_method["pix"]["percentage"] == pytest.approx(70.0)
    assert by_method["credit_card"]["total"] == "20.00"
    assert by_method["not_informed"]["total"] == "10.00"


async def test_monthly_paid_pending_splits_by_status(client: AsyncClient, make_user: Any) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Série mensal pago x pendente (pedido direto do usuário,
    fora de qualquer build-context) — mesmo recorte de
    `test_monthly_evolution_returns_requested_number_of_points`, mas
    quebrando a soma do mês por `PaymentStatus`.
    """
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    await _create_transaction(
        client, token, category_id, amount="60.00", date_str="2026-06-10", status="paid"
    )
    await _create_transaction(
        client, token, category_id, amount="25.00", date_str="2026-06-12", status="pending"
    )

    response = await client.get(
        "/api/v1/reports/monthly-paid-pending",
        headers=auth_headers(token),
        params={"year": 2026, "month": 6, "months": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert body[-1]["year"] == 2026
    assert body[-1]["month"] == 6
    assert body[-1]["total_paid"] == "60.00"
    assert body[-1]["total_pending"] == "25.00"
    assert body[0]["total_paid"] == "0.00"
    assert body[0]["total_pending"] == "0.00"


async def test_list_report_transactions_filters_by_category_and_paginates(
    client: AsyncClient, make_user: Any
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    other_category_id = await _create_private_category(client, token, "Lazer")

    await _create_transaction(client, token, category_id, description="A")
    await _create_transaction(client, token, category_id, description="B")
    await _create_transaction(client, token, other_category_id, description="C")

    response = await client.get(
        "/api/v1/reports/transactions",
        headers=auth_headers(token),
        params={
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "category_id": category_id,
            "page": 1,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 2
    assert body["pagination"]["total_pages"] == 2
    assert len(body["items"]) == 1


async def test_list_report_transactions_filters_by_payment_method(
    client: AsyncClient, make_user: Any
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: `payment_method` (pedido direto do usuário, fora de
    qualquer build-context) filtra em memória — alimenta o modal
    "despesas por tipo de pagamento" do Dashboard.
    """
    _, token = await make_user()
    category_id = await _global_category_id(client, token)

    await _create_transaction(client, token, category_id, description="A", payment_method="pix")
    await _create_transaction(
        client, token, category_id, description="B", payment_method="credit_card"
    )
    await _create_transaction(client, token, category_id, description="C")

    response = await client.get(
        "/api/v1/reports/transactions",
        headers=auth_headers(token),
        params={"date_from": "2026-06-01", "date_to": "2026-06-30", "payment_method": "pix"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["description"] == "A"


async def test_list_report_transactions_filters_by_not_informed_payment_method(
    client: AsyncClient, make_user: Any
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Bug real reportado pelo usuário — o modal de "Não
    informado" no Dashboard vinha sempre vazio, porque o filtro
    comparava o campo (sempre `None` pra quem não preencheu tipo de
    pagamento) contra a string literal `"not_informed"` (a chave que
    `get_payment_method_distribution` usa só pra exibição). `payment_
    method=not_informed` precisa casar com transações sem o campo
    preenchido, não com um valor gravado igual à chave.
    """
    _, token = await make_user()
    category_id = await _global_category_id(client, token)

    await _create_transaction(client, token, category_id, description="A", payment_method="pix")
    await _create_transaction(client, token, category_id, description="B")

    response = await client.get(
        "/api/v1/reports/transactions",
        headers=auth_headers(token),
        params={"date_from": "2026-06-01", "date_to": "2026-06-30", "payment_method": "not_informed"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["description"] == "B"


async def test_list_report_transactions_invalid_category_returns_404(
    client: AsyncClient, make_user: Any
) -> None:
    _, token = await make_user()

    response = await client.get(
        "/api/v1/reports/transactions",
        headers=auth_headers(token),
        params={
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "category_id": "not-a-valid-ulid",
        },
    )

    assert response.status_code == 404


async def test_export_csv_uses_semicolon_pt_br_format_and_bom(
    client: AsyncClient, make_user: Any
) -> None:
    _, token = await make_user()
    category_id = await _global_category_id(client, token)
    await _create_transaction(
        client, token, category_id, amount="1234.56", description="Compra grande", date_str="2026-06-15"
    )

    response = await client.get(
        "/api/v1/reports/export/csv",
        headers=auth_headers(token),
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    raw = response.content
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "Data;Descrição;Categoria;Valor"
    assert "15/06/2026" in lines[1]
    assert "1.234,56" in lines[1]


async def test_export_csv_empty_period_returns_only_header(
    client: AsyncClient, make_user: Any
) -> None:
    _, token = await make_user()

    response = await client.get(
        "/api/v1/reports/export/csv",
        headers=auth_headers(token),
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )

    assert response.status_code == 200
    text = response.content.decode("utf-8-sig")
    assert len(text.strip().splitlines()) == 1


async def test_generate_ai_narrative_use_case_returns_fixed_message_without_calling_provider(
    db_session: AsyncSession, make_user: Any
) -> None:
    """Período sem transações não chama o provider de IA (evita custo/throttle desnecessário)."""
    user, _ = await make_user()
    fake_chat_port = _FakeChatCompletionPort()
    use_case = GenerateAiNarrativeUseCase(
        SqlAlchemyReportsRepository(db_session),
        SqlAlchemyCategoryRepository(db_session),
        fake_chat_port,
        _FakeCheckAiUsageLimitUseCase(),
        _FakeRecordAiUsageUseCase(),
    )

    narrative = await use_case.execute(
        GenerateAiNarrativeInput(
            user_id=user.id,
            period=PeriodRange(start=Period(year=2026, month=1), end=Period(year=2026, month=1)),
            category_public_id=None,
            language=Language.PT_BR,
        )
    )

    assert narrative == "Não há transações registradas neste período."
    assert fake_chat_port.calls == 0


async def test_generate_ai_narrative_use_case_calls_provider_when_there_is_data(
    client: AsyncClient, db_session: AsyncSession, make_user: Any
) -> None:
    user, token = await make_user()
    category_id = await _global_category_id(client, token)
    await _create_transaction(client, token, category_id, amount="60.00", description="Padaria")

    fake_chat_port = _FakeChatCompletionPort(response="Você gastou pouco este mês.")
    use_case = GenerateAiNarrativeUseCase(
        SqlAlchemyReportsRepository(db_session),
        SqlAlchemyCategoryRepository(db_session),
        fake_chat_port,
        _FakeCheckAiUsageLimitUseCase(),
        _FakeRecordAiUsageUseCase(),
    )

    narrative = await use_case.execute(
        GenerateAiNarrativeInput(
            user_id=user.id,
            period=PeriodRange(start=Period(year=2026, month=6), end=Period(year=2026, month=6)),
            category_public_id=None,
            language=Language.EN,
        )
    )

    assert narrative == "Você gastou pouco este mês."
    assert fake_chat_port.calls == 1
    assert "English" in fake_chat_port.received_system_instruction
    assert "Padaria" not in fake_chat_port.received_system_instruction


async def test_post_narrative_enqueues_job(
    client: AsyncClient, make_user: Any, fake_arq_pool: FakeArqPool
) -> None:
    _, token = await make_user()

    response = await client.post(
        "/api/v1/reports/narrative",
        headers=auth_headers(token),
        json={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert len(fake_arq_pool.enqueued) == 1
    function_name, args = fake_arq_pool.enqueued[0]
    assert function_name == "generate_ai_narrative_job"
    assert args[1] == "2026-06-01"
    assert args[2] == "2026-06-30"


async def test_post_narrative_throttle_returns_429_after_limit(
    client: AsyncClient, make_user: Any
) -> None:
    _, token = await make_user()
    payload = {"date_from": "2026-06-01", "date_to": "2026-06-30"}

    for _ in range(10):
        response = await client.post(
            "/api/v1/reports/narrative", headers=auth_headers(token), json=payload
        )
        assert response.status_code == 202

    eleventh = await client.post(
        "/api/v1/reports/narrative", headers=auth_headers(token), json=payload
    )

    assert eleventh.status_code == 429
    assert "Retry-After" in eleventh.headers


async def test_report_view_token_reads_summary_but_cannot_generate_narrative(
    client: AsyncClient, make_user: Any
) -> None:
    """
    O token de link mágico do bot (`report_view`) autentica nos 5
    endpoints de leitura de `/reports` — aqui, `summary` — mas nunca em
    `/reports/narrative` (só `get_current_user`, tipo "access" estrito):
    o link enviado pelo WhatsApp não pode disparar geração de IA, só
    visualizar dados já calculados (2026-08-18).
    """
    user, _ = await make_user()
    report_view_token = JwtService().create_report_view_token(str(user.id))

    summary_response = await client.get(
        "/api/v1/reports/summary",
        headers=auth_headers(report_view_token),
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert summary_response.status_code == 200

    narrative_response = await client.post(
        "/api/v1/reports/narrative",
        headers=auth_headers(report_view_token),
        json={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert narrative_response.status_code == 401


async def test_report_view_token_lists_categories_but_cannot_create_one(
    client: AsyncClient, make_user: Any
) -> None:
    """
    O dropdown de filtro por categoria da tela de Relatórios
    compartilhada precisa de `GET /categories` funcionando com o token
    `report_view` — mas criar uma categoria continua exigindo um access
    token normal (2026-08-18).
    """
    user, _ = await make_user()
    report_view_token = JwtService().create_report_view_token(str(user.id))

    list_response = await client.get(
        "/api/v1/categories", headers=auth_headers(report_view_token)
    )
    assert list_response.status_code == 200

    create_response = await client.post(
        "/api/v1/categories",
        headers=auth_headers(report_view_token),
        json={"name": "Categoria via link", "color": "#6366f1", "icon": "tag"},
    )
    assert create_response.status_code == 401


async def test_get_dashboard_layout_returns_null_layout_for_new_user(
    client: AsyncClient, make_user: Any
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Conta nova nunca personalizou o Dashboard — `layout=None`
    sinaliza pro frontend usar o layout padrão (pedido direto do
    usuário, fora de qualquer build-context).
    """
    _, token = await make_user()

    response = await client.get("/api/v1/reports/dashboard-layout", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json() == {"layout": None}


async def test_update_dashboard_layout_persists_visibility_and_order(
    client: AsyncClient, make_user: Any
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: `PUT` salva a lista inteira (visibilidade + ordem); um
    `GET` seguinte devolve exatamente o que foi salvo, na mesma ordem.
    """
    _, token = await make_user()
    layout = [
        {"card": "recent_transactions", "visible": True},
        {"card": "monthly_trend", "visible": False},
        {"card": "category_composition", "visible": True},
        {"card": "category_distribution", "visible": True},
        {"card": "payment_method_distribution", "visible": False},
        {"card": "paid_pending", "visible": True},
    ]

    put_response = await client.put(
        "/api/v1/reports/dashboard-layout", headers=auth_headers(token), json={"layout": layout}
    )
    assert put_response.status_code == 200
    assert put_response.json() == {"layout": layout}

    get_response = await client.get("/api/v1/reports/dashboard-layout", headers=auth_headers(token))
    assert get_response.status_code == 200
    assert get_response.json() == {"layout": layout}


async def test_update_dashboard_layout_rejects_unknown_card(
    client: AsyncClient, make_user: Any
) -> None:
    """Um `card` fora do conjunto fechado de 6 valores é rejeitado com 422, não silenciosamente aceito."""
    _, token = await make_user()

    response = await client.put(
        "/api/v1/reports/dashboard-layout",
        headers=auth_headers(token),
        json={"layout": [{"card": "not_a_real_card", "visible": True}]},
    )

    assert response.status_code == 422
