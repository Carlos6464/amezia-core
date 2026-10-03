import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.domain.reports.value_objects import (
    CategoryDistributionItem,
    CategorySummary,
    FinancialSummary,
    MonthlyEvolutionPoint,
    MonthlyPaidPendingPoint,
    Page,
    PaymentMethodDistributionItem,
    TransactionSummary,
)
from src.domain.user.value_objects import DashboardCardPreference

DashboardCardLiteral = Literal[
    "monthly_trend",
    "category_composition",
    "category_distribution",
    "recent_transactions",
    "payment_method_distribution",
    "paid_pending",
]


def _cents_to_decimal(cents: int) -> Decimal:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Converte centavos (`int`) para Decimal com 2 casas —
    mesmo padrão de `transactions/router.py::_cents_to_decimal`, sem
    reaproveitar `Money` (que rejeita valores <= 0).
    """
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


class PeriodRangeResponse(BaseModel):
    date_from: dt.date
    date_to: dt.date


class TopCategoryResponse(BaseModel):
    category_id: str
    name: str
    total: Decimal
    percentage: float

    @classmethod
    def from_vo(cls, vo: CategorySummary) -> "TopCategoryResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Converte a VO de domínio `CategorySummary` (usada
        como "maior categoria") no schema de resposta HTTP.
        """
        return cls(
            category_id=vo.category_id,
            name=vo.category_name,
            total=_cents_to_decimal(vo.total),
            percentage=vo.percentage,
        )


class BiggestTransactionResponse(BaseModel):
    public_id: str
    description: str
    amount: Decimal
    category_name: str
    occurred_at: dt.date

    @classmethod
    def from_vo(cls, vo: TransactionSummary) -> "BiggestTransactionResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Converte a VO de domínio `TransactionSummary` (usada
        como "maior transação") no schema de resposta HTTP.
        """
        return cls(
            public_id=vo.public_id,
            description=vo.description,
            amount=vo.amount.to_decimal(),
            category_name=vo.category_name,
            occurred_at=vo.occurred_at,
        )


class FinancialSummaryResponse(BaseModel):
    period: PeriodRangeResponse
    total_expense: Decimal
    transaction_count: int
    top_category: TopCategoryResponse | None
    biggest_transaction: BiggestTransactionResponse | None

    @classmethod
    def from_vo(cls, vo: FinancialSummary) -> "FinancialSummaryResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Converte `FinancialSummary` (domínio) no schema de
        resposta de `GET /reports/summary` (build-context-05 §2.5). Sem
        `total_income`/`balance`: produto é expense-only (2026-08-14).
        """
        date_from, date_to = vo.period.date_range()
        return cls(
            period=PeriodRangeResponse(date_from=date_from, date_to=date_to),
            total_expense=_cents_to_decimal(vo.total_expense),
            transaction_count=vo.transaction_count,
            top_category=TopCategoryResponse.from_vo(vo.top_category) if vo.top_category else None,
            biggest_transaction=(
                BiggestTransactionResponse.from_vo(vo.biggest_transaction)
                if vo.biggest_transaction
                else None
            ),
        )


class MonthlyEvolutionPointResponse(BaseModel):
    year: int
    month: int
    total_expense: Decimal

    @classmethod
    def from_vo(cls, vo: MonthlyEvolutionPoint) -> "MonthlyEvolutionPointResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Converte um `MonthlyEvolutionPoint` (domínio) no
        schema de resposta de `GET /reports/monthly-evolution`.
        """
        return cls(
            year=vo.period.year,
            month=vo.period.month or 1,
            total_expense=_cents_to_decimal(vo.total_expense),
        )


class CategoryDistributionItemResponse(BaseModel):
    category_id: str
    name: str
    color: str
    total: Decimal
    percentage: float

    @classmethod
    def from_vo(cls, vo: CategoryDistributionItem) -> "CategoryDistributionItemResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Converte um `CategoryDistributionItem` (domínio) no
        schema de resposta de `GET /reports/category-distribution`.
        """
        return cls(
            category_id=vo.category_id,
            name=vo.category_name,
            color=vo.color,
            total=_cents_to_decimal(vo.total),
            percentage=vo.percentage,
        )


class MonthlyPaidPendingPointResponse(BaseModel):
    year: int
    month: int
    total_paid: Decimal
    total_pending: Decimal

    @classmethod
    def from_vo(cls, vo: MonthlyPaidPendingPoint) -> "MonthlyPaidPendingPointResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Converte um `MonthlyPaidPendingPoint` (domínio) no
        schema de resposta de `GET /reports/monthly-paid-pending`.
        """
        return cls(
            year=vo.period.year,
            month=vo.period.month or 1,
            total_paid=_cents_to_decimal(vo.total_paid),
            total_pending=_cents_to_decimal(vo.total_pending),
        )


class PaymentMethodDistributionItemResponse(BaseModel):
    payment_method: str
    total: Decimal
    percentage: float

    @classmethod
    def from_vo(cls, vo: PaymentMethodDistributionItem) -> "PaymentMethodDistributionItemResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Converte um `PaymentMethodDistributionItem` (domínio)
        no schema de resposta de `GET /reports/payment-method-distribution`
        — `payment_method` aqui é sempre uma string não-vazia (`"not_informed"`
        substitui `None`, resolvido já na agregação do repositório).
        """
        return cls(
            payment_method=vo.payment_method,
            total=_cents_to_decimal(vo.total),
            percentage=vo.percentage,
        )


class ReportTransactionResponse(BaseModel):
    public_id: str
    occurred_at: dt.date
    description: str
    category_id: str
    category_name: str
    amount: Decimal

    @classmethod
    def from_vo(cls, vo: TransactionSummary) -> "ReportTransactionResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Converte um `TransactionSummary` (domínio) numa linha
        da tabela paginada de `GET /reports/transactions`.
        """
        return cls(
            public_id=vo.public_id,
            occurred_at=vo.occurred_at,
            description=vo.description,
            category_id=vo.category_id,
            category_name=vo.category_name,
            amount=vo.amount.to_decimal(),
        )


class ReportsPaginationInfo(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedTransactionsResponse(BaseModel):
    items: list[ReportTransactionResponse]
    pagination: ReportsPaginationInfo

    @classmethod
    def from_page(cls, page: Page[TransactionSummary]) -> "PaginatedTransactionsResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Converte a `Page[TransactionSummary]` (domínio) na
        resposta paginada HTTP.
        """
        return cls(
            items=[ReportTransactionResponse.from_vo(item) for item in page.items],
            pagination=ReportsPaginationInfo(
                page=page.page,
                page_size=page.page_size,
                total=page.total,
                total_pages=page.total_pages,
            ),
        )


class DashboardCardPreferenceSchema(BaseModel):
    card: DashboardCardLiteral
    visible: bool

    @classmethod
    def from_vo(cls, vo: DashboardCardPreference) -> "DashboardCardPreferenceSchema":
        return cls(card=vo.card.value, visible=vo.visible)


class DashboardLayoutResponse(BaseModel):
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Resposta de `GET`/`PUT /reports/dashboard-layout` —
    `layout=None` significa "usuário nunca personalizou", o frontend
    decide o layout padrão nesse caso (não é responsabilidade do
    backend saber qual é o layout "de fábrica" da UI).
    """

    layout: list[DashboardCardPreferenceSchema] | None

    @classmethod
    def from_vo(cls, layout: list[DashboardCardPreference] | None) -> "DashboardLayoutResponse":
        return cls(
            layout=[DashboardCardPreferenceSchema.from_vo(item) for item in layout]
            if layout is not None
            else None
        )


class UpdateDashboardLayoutRequest(BaseModel):
    layout: list[DashboardCardPreferenceSchema] = Field(min_length=1, max_length=12)


class NarrativeRequest(BaseModel):
    date_from: dt.date
    date_to: dt.date
    category_id: str | None = None


class NarrativeQueuedResponse(BaseModel):
    status: str = "queued"
