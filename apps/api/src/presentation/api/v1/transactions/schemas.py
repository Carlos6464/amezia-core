import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.application.transaction.dtos import CategorySummary as CategorySummaryDto
from src.application.transaction.dtos import RecurrenceWithCategory, TransactionWithCategory
from src.application.transaction.use_cases.list_transactions import TransactionListResult

TransactionTypeLiteral = Literal["income", "expense"]
PaymentStatusLiteral = Literal["pending", "paid"]
RecurrenceFrequencyLiteral = Literal["weekly", "monthly", "yearly"]


class CategorySummaryResponse(BaseModel):
    public_id: str
    name: str
    color: str

    @classmethod
    def from_dto(cls, dto: CategorySummaryDto) -> "CategorySummaryResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte o DTO de aplicação CategorySummary no schema
        de resposta HTTP.
        """
        return cls(public_id=dto.public_id, name=dto.name, color=dto.color)


class InstallmentRequest(BaseModel):
    total: int = Field(ge=2, le=60)


class InstallmentResponse(BaseModel):
    group_id: str
    number: int
    total: int


class RecurrenceRequest(BaseModel):
    frequency: RecurrenceFrequencyLiteral
    end_date: dt.date | None = None


class TransactionCreateRequest(BaseModel):
    category_id: str = Field(description="public_id (ULID) da categoria — nunca o id interno")
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str = Field(min_length=1)
    date: dt.date
    status: PaymentStatusLiteral = "paid"
    payment_method: str | None = Field(default=None, max_length=1000)
    installment: InstallmentRequest | None = None
    recurrence: RecurrenceRequest | None = None

    @model_validator(mode="after")
    def check_installment_recurrence_mutually_exclusive(self) -> "TransactionCreateRequest":
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: `installment` e `recurrence` representam mecanismos
        incompatíveis (build-context-03 §2.7) — rejeita o request com
        422 se os dois vierem preenchidos, antes de chegar no use case.
        """
        if self.installment is not None and self.recurrence is not None:
            raise ValueError("installment and recurrence are mutually exclusive")
        return self


class TransactionUpdateRequest(BaseModel):
    category_id: str | None = None
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    description: str | None = Field(default=None, min_length=1)
    date: dt.date | None = None
    status: PaymentStatusLiteral | None = None
    payment_method: str | None = Field(default=None, max_length=1000)
    paid_at: dt.date | None = None


class TransactionResponse(BaseModel):
    public_id: str
    type: TransactionTypeLiteral
    amount: Decimal
    description: str
    date: dt.date
    status: PaymentStatusLiteral
    payment_method: str | None
    paid_at: dt.date | None
    category: CategorySummaryResponse
    receipt_url: str | None
    installment: InstallmentResponse | None
    is_recurring: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    @classmethod
    def from_dto(
        cls, dto: TransactionWithCategory, receipt_url: str | None = None
    ) -> "TransactionResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte a DTO de aplicação TransactionWithCategory no
        schema de resposta HTTP. `receipt_url` é passado à parte (não
        vem no DTO) porque é uma URL assinada gerada sob demanda pelo
        router (build-context-03 §2.8), não um dado persistido.
        """
        transaction = dto.transaction
        installment = None
        if transaction.installment_group_id is not None:
            installment = InstallmentResponse(
                group_id=str(transaction.installment_group_id),
                number=transaction.installment_number,
                total=transaction.installment_total,
            )
        return cls(
            public_id=str(transaction.public_id),
            type=transaction.type.value,
            amount=transaction.amount.to_decimal(),
            description=transaction.description,
            date=transaction.date,
            status=transaction.status.value,
            payment_method=transaction.payment_method,
            paid_at=transaction.paid_at,
            category=CategorySummaryResponse.from_dto(dto.category),
            receipt_url=receipt_url,
            installment=installment,
            is_recurring=transaction.recurrence_rule_id is not None,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
        )


class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class TransactionSummaryResponse(BaseModel):
    total_amount: Decimal
    count: int
    budget_limit: Decimal | None
    budget_used_percentage: float | None


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    pagination: PaginationInfo
    summary: TransactionSummaryResponse

    @classmethod
    def from_result(
        cls,
        result: TransactionListResult,
        receipt_urls: dict[str, str | None],
        page: int,
        page_size: int,
    ) -> "TransactionListResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte o resultado de ListTransactionsUseCase na
        resposta HTTP paginada — `summary` reflete o conjunto filtrado
        completo (`result.total`/`result.total_amount_cents`), não só a
        página atual (build-context-03 §2.6).
        """
        total_pages = (result.total + page_size - 1) // page_size if page_size else 0
        budget_limit = (
            (Decimal(result.budget_limit_cents) / 100).quantize(Decimal("0.01"))
            if result.budget_limit_cents is not None
            else None
        )
        return cls(
            items=[
                TransactionResponse.from_dto(
                    item, receipt_url=receipt_urls.get(str(item.transaction.public_id))
                )
                for item in result.items
            ],
            pagination=PaginationInfo(
                page=page, page_size=page_size, total=result.total, total_pages=total_pages
            ),
            summary=TransactionSummaryResponse(
                total_amount=(Decimal(result.total_amount_cents) / 100).quantize(Decimal("0.01")),
                count=result.total,
                budget_limit=budget_limit,
                budget_used_percentage=result.budget_used_percentage,
            ),
        )


class BulkDeleteRequest(BaseModel):
    public_ids: list[str] = Field(min_length=1)


class BulkDeleteResponse(BaseModel):
    deleted_count: int
    requested_count: int


class RecurrenceResponse(BaseModel):
    public_id: str
    type: TransactionTypeLiteral
    amount: Decimal
    description: str
    category: CategorySummaryResponse
    frequency: RecurrenceFrequencyLiteral
    start_date: dt.date
    end_date: dt.date | None
    next_occurrence_date: dt.date

    @classmethod
    def from_dto(cls, dto: RecurrenceWithCategory) -> "RecurrenceResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte a DTO RecurrenceWithCategory no schema de
        resposta HTTP.
        """
        rule = dto.rule
        return cls(
            public_id=str(rule.public_id),
            type=rule.type.value,
            amount=rule.amount.to_decimal(),
            description=rule.description,
            category=CategorySummaryResponse.from_dto(dto.category),
            frequency=rule.frequency.value,
            start_date=rule.start_date,
            end_date=rule.end_date,
            next_occurrence_date=rule.next_occurrence_date,
        )


class BudgetResponse(BaseModel):
    monthly_budget: Decimal | None


class BudgetUpdateRequest(BaseModel):
    monthly_budget: Decimal | None = Field(default=None, ge=0, decimal_places=2)
