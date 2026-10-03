import datetime as dt

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reports.use_cases.export_transactions_csv import (
    ExportTransactionsCsvInput,
    ExportTransactionsCsvUseCase,
)
from src.application.reports.use_cases.get_category_distribution import (
    GetCategoryDistributionInput,
    GetCategoryDistributionUseCase,
)
from src.application.reports.use_cases.get_dashboard_layout import GetDashboardLayoutUseCase
from src.application.reports.use_cases.get_financial_summary import (
    GetFinancialSummaryInput,
    GetFinancialSummaryUseCase,
)
from src.application.reports.use_cases.get_monthly_evolution import (
    DEFAULT_MONTHS,
    GetMonthlyEvolutionInput,
    GetMonthlyEvolutionUseCase,
)
from src.application.reports.use_cases.get_monthly_paid_pending import (
    DEFAULT_MONTHS as PAID_PENDING_DEFAULT_MONTHS,
)
from src.application.reports.use_cases.get_monthly_paid_pending import (
    GetMonthlyPaidPendingInput,
    GetMonthlyPaidPendingUseCase,
)
from src.application.reports.use_cases.get_payment_method_distribution import (
    GetPaymentMethodDistributionInput,
    GetPaymentMethodDistributionUseCase,
)
from src.application.reports.use_cases.list_report_transactions import (
    ListReportTransactionsInput,
    ListReportTransactionsUseCase,
)
from src.application.reports.use_cases.update_dashboard_layout import (
    UpdateDashboardLayoutInput,
    UpdateDashboardLayoutUseCase,
)
from src.domain.category.exceptions import CategoryNotFoundError
from src.domain.reports.value_objects import PeriodRange
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.value_objects import Period
from src.domain.user.entities import User
from src.domain.user.value_objects import DashboardCard, DashboardCardPreference
from src.infrastructure.database.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_reports_repository import (
    SqlAlchemyReportsRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyCsvExportEventRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.infrastructure.queue.pool import get_arq_pool
from src.presentation.api.v1.dependencies.auth import (
    get_current_user,
    get_current_user_or_report_viewer,
)
from src.presentation.api.v1.reports.dependencies import (
    enforce_ai_narrative_throttle,
    enforce_csv_export_limit,
)
from src.presentation.api.v1.reports.schemas import (
    CategoryDistributionItemResponse,
    DashboardLayoutResponse,
    FinancialSummaryResponse,
    MonthlyEvolutionPointResponse,
    MonthlyPaidPendingPointResponse,
    NarrativeQueuedResponse,
    NarrativeRequest,
    PaginatedTransactionsResponse,
    PaymentMethodDistributionItemResponse,
    UpdateDashboardLayoutRequest,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _parse_category_public_id(raw: str | None) -> PublicId | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Faz o parse do `category_id` opcional (public_id ULID)
    recebido do cliente. Um ULID malformado é tratado como "não
    encontrado" (404), nunca como erro de validação — mesmo padrão de
    `transactions/router.py::_parse_category_public_id` (RN-01, não
    revela detalhe interno).
    """
    if raw is None:
        return None
    try:
        return PublicId(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc


def _period_range(date_from: dt.date, date_to: dt.date) -> PeriodRange:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Converte o par `date_from`/`date_to` recebido na
    querystring/body num `PeriodRange` (mês/ano) — o frontend sempre
    envia o 1º dia do mês de início e o último dia do mês de fim (o
    period-range-picker só deixa escolher mês/ano), então descartar o
    dia exato é seguro.
    """
    return PeriodRange(
        start=Period(year=date_from.year, month=date_from.month),
        end=Period(year=date_to.year, month=date_to.month),
    )


@router.get("/summary", response_model=FinancialSummaryResponse)
async def get_financial_summary(
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> FinancialSummaryResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: GET /reports/summary — resumo financeiro do período
    (build-context-05 §2.5). Aceita `report_view` (link mágico do bot,
    2026-08-18) além do access token normal — ver
    `get_current_user_or_report_viewer`.
    """
    use_case = GetFinancialSummaryUseCase(SqlAlchemyReportsRepository(db))
    summary = await use_case.execute(
        GetFinancialSummaryInput(
            user_id=current_user.id,
            period=_period_range(date_from, date_to),
        )
    )
    return FinancialSummaryResponse.from_vo(summary)


@router.get("/monthly-evolution", response_model=list[MonthlyEvolutionPointResponse])
async def get_monthly_evolution(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    months: int = Query(default=DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[MonthlyEvolutionPointResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: GET /reports/monthly-evolution — série mensal de
    despesas dos `months` meses corridos até `year`/`month` (inclusive),
    usada pelo line-chart do Dashboard.
    """
    use_case = GetMonthlyEvolutionUseCase(SqlAlchemyReportsRepository(db))
    points = await use_case.execute(
        GetMonthlyEvolutionInput(
            user_id=current_user.id,
            reference_period=Period(year=year, month=month),
            months=months,
        )
    )
    return [MonthlyEvolutionPointResponse.from_vo(point) for point in points]


@router.get("/monthly-paid-pending", response_model=list[MonthlyPaidPendingPointResponse])
async def get_monthly_paid_pending(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    months: int = Query(default=PAID_PENDING_DEFAULT_MONTHS, ge=1, le=24),
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[MonthlyPaidPendingPointResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: GET /reports/monthly-paid-pending — série mensal pago x
    pendente dos `months` meses corridos até `year`/`month` (inclusive),
    usada pelo gráfico de barra dupla do Dashboard/Reports (pedido
    direto do usuário, fora de qualquer build-context).
    """
    use_case = GetMonthlyPaidPendingUseCase(SqlAlchemyReportsRepository(db))
    points = await use_case.execute(
        GetMonthlyPaidPendingInput(
            user_id=current_user.id,
            reference_period=Period(year=year, month=month),
            months=months,
        )
    )
    return [MonthlyPaidPendingPointResponse.from_vo(point) for point in points]


@router.get("/category-distribution", response_model=list[CategoryDistributionItemResponse])
async def get_category_distribution(
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryDistributionItemResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: GET /reports/category-distribution — distribuição por
    categoria do período, ordenada por total desc.
    """
    use_case = GetCategoryDistributionUseCase(SqlAlchemyReportsRepository(db))
    items = await use_case.execute(
        GetCategoryDistributionInput(
            user_id=current_user.id,
            period=_period_range(date_from, date_to),
        )
    )
    return [CategoryDistributionItemResponse.from_vo(item) for item in items]


@router.get("/payment-method-distribution", response_model=list[PaymentMethodDistributionItemResponse])
async def get_payment_method_distribution(
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentMethodDistributionItemResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: GET /reports/payment-method-distribution — distribuição
    por tipo de pagamento do período, ordenada por total desc (pedido
    direto do usuário, fora de qualquer build-context).
    """
    use_case = GetPaymentMethodDistributionUseCase(SqlAlchemyReportsRepository(db))
    items = await use_case.execute(
        GetPaymentMethodDistributionInput(
            user_id=current_user.id,
            period=_period_range(date_from, date_to),
        )
    )
    return [PaymentMethodDistributionItemResponse.from_vo(item) for item in items]


@router.get("/dashboard-layout", response_model=DashboardLayoutResponse)
async def get_dashboard_layout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardLayoutResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: GET /reports/dashboard-layout — quais cards do Dashboard
    o usuário autenticado deixou visíveis e em que ordem (pedido direto
    do usuário, fora de qualquer build-context). Nunca aceita o token
    de link mágico do bot (`get_current_user`, não `_or_report_viewer`)
    — é uma preferência pessoal de UI, não um dado de relatório.
    """
    use_case = GetDashboardLayoutUseCase(SqlAlchemyUserRepository(db))
    layout = await use_case.execute(current_user.id)
    return DashboardLayoutResponse.from_vo(layout)


@router.put("/dashboard-layout", response_model=DashboardLayoutResponse)
async def update_dashboard_layout(
    payload: UpdateDashboardLayoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardLayoutResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: PUT /reports/dashboard-layout — salva o layout completo
    (visibilidade + ordem dos 6 cards personalizáveis) de uma vez.
    """
    use_case = UpdateDashboardLayoutUseCase(SqlAlchemyUserRepository(db))
    layout = await use_case.execute(
        UpdateDashboardLayoutInput(
            user_id=current_user.id,
            layout=[
                DashboardCardPreference(card=DashboardCard(item.card), visible=item.visible)
                for item in payload.layout
            ],
        )
    )
    await db.commit()
    return DashboardLayoutResponse.from_vo(layout)


@router.get("/transactions", response_model=PaginatedTransactionsResponse)
async def list_report_transactions(
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
    category_id: str | None = Query(default=None),
    payment_method: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=100),
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTransactionsResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: GET /reports/transactions — tabela paginada de transações
    do intervalo, com filtro opcional de `category_id` e, desde
    2026-09-15 (fora de qualquer build-context), `payment_method` —
    alimenta o modal "despesas por tipo de pagamento" do Dashboard.
    """
    use_case = ListReportTransactionsUseCase(
        SqlAlchemyReportsRepository(db), SqlAlchemyCategoryRepository(db)
    )
    try:
        page_result = await use_case.execute(
            ListReportTransactionsInput(
                user_id=current_user.id,
                period=_period_range(date_from, date_to),
                category_public_id=_parse_category_public_id(category_id),
                page=page,
                page_size=page_size,
                payment_method=payment_method,
            )
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc

    return PaginatedTransactionsResponse.from_page(page_result)


@router.get("/export/csv", dependencies=[Depends(enforce_csv_export_limit)])
async def export_transactions_csv(
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
    category_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: GET /reports/export/csv — exporta o filtro inteiro como
    CSV (`;`, formato pt-BR fixo, BOM UTF-8, build-context-05 §2.6).
    `enforce_csv_export_limit` (build-context-09 §2.6) bloqueia com 403
    antes de chegar aqui se o plano do usuário já bateu o limite mensal
    — gerado com sucesso, grava uma linha em `csv_export_events` pra
    contar contra o próximo limite.
    """
    use_case = ExportTransactionsCsvUseCase(
        SqlAlchemyReportsRepository(db), SqlAlchemyCategoryRepository(db)
    )
    try:
        content = await use_case.execute(
            ExportTransactionsCsvInput(
                user_id=current_user.id,
                period=_period_range(date_from, date_to),
                category_public_id=_parse_category_public_id(category_id),
                language=current_user.language,
            )
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc

    await SqlAlchemyCsvExportEventRepository(db).create(current_user.id)
    await db.commit()

    filename = f"relatorio-{date_from.isoformat()}_{date_to.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/narrative",
    response_model=NarrativeQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(enforce_ai_narrative_throttle)],
)
async def generate_ai_narrative(
    payload: NarrativeRequest,
    current_user: User = Depends(get_current_user),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> NarrativeQueuedResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: POST /reports/narrative — enfileira `generate_ai_narrative_job`
    e responde imediatamente; a narrativa chega depois via WebSocket
    (`report.narrative.ready`/`report.narrative.failed`, build-context-05
    §2.7). Throttle (10/min por usuário) checado antes de enfileirar via
    a dependency `enforce_ai_narrative_throttle`.
    """
    await arq_pool.enqueue_job(
        "generate_ai_narrative_job",
        str(current_user.id),
        payload.date_from.isoformat(),
        payload.date_to.isoformat(),
        payload.category_id,
    )
    return NarrativeQueuedResponse()
