from decimal import ROUND_HALF_UP, Decimal

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.transaction.dtos import RecurrenceWithCategory, TransactionWithCategory
from src.application.transaction.use_cases.cancel_recurrence import (
    CancelRecurrenceInput,
    CancelRecurrenceUseCase,
)
from src.application.transaction.use_cases.create_recurring_transaction import (
    CreateRecurringTransactionUseCase,
)
from src.application.transaction.use_cases.create_transaction import (
    CreateTransactionInput,
    CreateTransactionUseCase,
    InstallmentInput,
    RecurrenceInput,
)
from src.application.transaction.use_cases.delete_receipt import (
    DeleteReceiptInput,
    DeleteReceiptUseCase,
)
from src.application.transaction.use_cases.delete_transaction import (
    DeleteTransactionInput,
    DeleteTransactionUseCase,
)
from src.application.transaction.use_cases.delete_transactions_bulk import (
    DeleteTransactionsBulkInput,
    DeleteTransactionsBulkUseCase,
)
from src.application.transaction.use_cases.get_budget import GetBudgetUseCase
from src.application.transaction.use_cases.get_transaction import GetTransactionUseCase
from src.application.transaction.use_cases.list_recurrences import ListRecurrencesUseCase
from src.application.transaction.use_cases.list_transactions import ListTransactionsUseCase
from src.application.transaction.use_cases.update_budget import (
    UpdateBudgetInput,
    UpdateBudgetUseCase,
)
from src.application.transaction.use_cases.update_transaction import (
    UpdateTransactionInput,
    UpdateTransactionUseCase,
)
from src.application.transaction.use_cases.upload_receipt import (
    UploadReceiptInput,
    UploadReceiptUseCase,
)
from src.domain.category.exceptions import CategoryNotFoundError
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.exceptions import (
    InvalidReceiptFileError,
    InvalidTransactionAmountError,
    RecurrenceRuleNotFoundError,
    TransactionNotFoundError,
)
from src.domain.transaction.repository import TransactionFilters
from src.domain.transaction.value_objects import (
    PaymentStatus,
    Period,
    RecurrenceFrequency,
    TransactionType,
)
from src.domain.user.entities import User
from src.infrastructure.database.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from src.infrastructure.database.repositories.recurrence_rule_repository import (
    SqlAlchemyRecurrenceRuleRepository,
)
from src.infrastructure.database.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.infrastructure.queue.pool import get_arq_pool
from src.infrastructure.storage.backblaze_client import BackblazeStorageClient
from src.presentation.api.v1.dependencies.auth import get_current_user
from src.presentation.api.v1.transactions.schemas import (
    BudgetResponse,
    BudgetUpdateRequest,
    BulkDeleteRequest,
    BulkDeleteResponse,
    RecurrenceResponse,
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _parse_transaction_public_id(raw: str) -> PublicId:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Faz o parse do public_id de transação vindo da URL. Um
    ULID malformado é tratado como "não encontrado" (404), nunca como
    erro de validação — RN-01 (não revelar detalhe interno).
    """
    try:
        return PublicId(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found") from exc


def _parse_category_public_id(raw: str) -> PublicId:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Mesmo tratamento de `_parse_transaction_public_id`, mas
    para o `category_id` (public_id de categoria) recebido no corpo da
    requisição — mensagem de erro própria.
    """
    try:
        return PublicId(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc


def _parse_recurrence_public_id(raw: str) -> PublicId:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Mesmo tratamento de `_parse_transaction_public_id`, mas
    para o `public_id` de uma RecurrenceRule.
    """
    try:
        return PublicId(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurrence not found") from exc


def _receipt_url(receipt_key: str | None) -> str | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Gera a URL assinada (presigned GET) do comprovante sob
    demanda — nunca persistida (build-context-03 §2.8). Não instancia o
    client do Backblaze quando não há comprovante, para não exigir B2
    configurado em respostas que não precisam dele.
    """
    if receipt_key is None:
        return None
    return BackblazeStorageClient().generate_presigned_url(receipt_key)


def _to_cents(amount: Decimal) -> int:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Converte um Decimal (unidade cheia) para centavos —
    usado só pelo teto mensal, que (diferente de `Money`) aceita zero,
    então não reaproveita `Money.from_decimal` (que exige > 0).
    """
    return int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _cents_to_decimal(cents: int | None) -> Decimal | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Converte centavos de volta para Decimal (2 casas) —
    usado pelas respostas de teto mensal.
    """
    if cents is None:
        return None
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def _transaction_response(result: TransactionWithCategory) -> TransactionResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Monta a resposta HTTP de uma transação a partir da DTO de
    aplicação, resolvendo a URL do comprovante sob demanda.
    """
    return TransactionResponse.from_dto(
        result, receipt_url=_receipt_url(result.transaction.receipt_key)
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> TransactionResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: POST /transactions — cria uma transação simples,
    parcelada (`installment`) ou recorrente (`recurrence`), conforme o
    corpo da requisição (build-context-03 §2.7). Desde o
    build-context-04, também enfileira a indexação de embedding de cada
    transação criada (RAG do Agente de IA). `type` sempre `EXPENSE`
    (não vem mais do payload): o produto é só de despesas — pedido do
    usuário em 2026-08-14, ver DIARIO.md. `TransactionType.INCOME`
    continua existindo no domínio (nenhuma migration foi feita), só
    nunca é escolhido a partir daqui.
    """
    transaction_repository = SqlAlchemyTransactionRepository(db)
    category_repository = SqlAlchemyCategoryRepository(db)
    recurrence_rule_repository = SqlAlchemyRecurrenceRuleRepository(db)
    recurring_use_case = CreateRecurringTransactionUseCase(
        transaction_repository, recurrence_rule_repository
    )
    use_case = CreateTransactionUseCase(
        transaction_repository, category_repository, recurring_use_case, arq_pool
    )

    installment_input = (
        InstallmentInput(total=payload.installment.total) if payload.installment else None
    )
    recurrence_input = (
        RecurrenceInput(
            frequency=RecurrenceFrequency(payload.recurrence.frequency),
            end_date=payload.recurrence.end_date,
        )
        if payload.recurrence
        else None
    )

    try:
        result = await use_case.execute(
            CreateTransactionInput(
                user_id=current_user.id,
                category_public_id=_parse_category_public_id(payload.category_id),
                type=TransactionType.EXPENSE,
                amount=payload.amount,
                description=payload.description,
                date=payload.date,
                status=PaymentStatus(payload.status),
                payment_method=payload.payment_method,
                installment=installment_input,
                recurrence=recurrence_input,
            )
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc
    except InvalidTransactionAmountError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Amount must be greater than zero"
        ) from exc

    await db.commit()
    return _transaction_response(result)


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    type: TransactionType | None = Query(default=None),
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: GET /transactions — lista paginada com filtros (2.5) e
    `summary` incluindo o teto mensal quando o período resolve para um
    único mês (2.9). `month` sozinho (sem `year`) é rejeitado — não faz
    sentido filtrar um mês sem saber de qual ano.
    """
    if month is not None and year is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "year is required when month is informed"
        )

    filters = TransactionFilters(
        type=type,
        status=status_filter,
        period=Period(year=year, month=month) if year is not None else None,
        q=q,
    )

    transaction_repository = SqlAlchemyTransactionRepository(db)
    category_repository = SqlAlchemyCategoryRepository(db)
    user_repository = SqlAlchemyUserRepository(db)
    use_case = ListTransactionsUseCase(transaction_repository, category_repository, user_repository)

    result = await use_case.execute(current_user.id, filters, page, page_size)
    receipt_urls = {
        str(item.transaction.public_id): _receipt_url(item.transaction.receipt_key)
        for item in result.items
    }
    return TransactionListResponse.from_result(result, receipt_urls, page, page_size)


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_transactions(
    payload: BulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BulkDeleteResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: POST /transactions/bulk-delete — exclui várias
    transações numa única operação (ex.: todas as parcelas de uma
    mesma compra). Idempotente: `public_id`s malformados, inexistentes
    ou de outro usuário são ignorados, mas ainda contam em
    `requested_count`.
    """
    valid_public_ids: list[PublicId] = []
    for raw in payload.public_ids:
        try:
            valid_public_ids.append(PublicId(raw))
        except ValueError:
            continue

    use_case = DeleteTransactionsBulkUseCase(SqlAlchemyTransactionRepository(db))
    result = await use_case.execute(
        DeleteTransactionsBulkInput(user_id=current_user.id, public_ids=valid_public_ids)
    )
    await db.commit()
    return BulkDeleteResponse(
        deleted_count=result.deleted_count, requested_count=len(payload.public_ids)
    )


@router.get("/recurrences", response_model=list[RecurrenceResponse])
async def list_recurrences(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[RecurrenceResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: GET /transactions/recurrences — regras de recorrência
    ativas do usuário autenticado.
    """
    use_case = ListRecurrencesUseCase(
        SqlAlchemyRecurrenceRuleRepository(db), SqlAlchemyCategoryRepository(db)
    )
    rules: list[RecurrenceWithCategory] = await use_case.execute(current_user.id)
    return [RecurrenceResponse.from_dto(rule) for rule in rules]


@router.delete("/recurrences/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_recurrence(
    public_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: DELETE /transactions/recurrences/{public_id} — cancela
    (desativa) a recorrência, sem apagar transações já geradas.
    """
    use_case = CancelRecurrenceUseCase(SqlAlchemyRecurrenceRuleRepository(db))
    try:
        await use_case.execute(
            CancelRecurrenceInput(
                user_id=current_user.id, public_id=_parse_recurrence_public_id(public_id)
            )
        )
    except RecurrenceRuleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurrence not found") from exc
    await db.commit()


@router.get("/budget", response_model=BudgetResponse)
async def get_budget(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> BudgetResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: GET /transactions/budget — teto mensal configurado
    (global por usuário, `None` se ainda não definido).
    """
    use_case = GetBudgetUseCase(SqlAlchemyUserRepository(db))
    monthly_budget_cents = await use_case.execute(current_user.id)
    return BudgetResponse(monthly_budget=_cents_to_decimal(monthly_budget_cents))


@router.put("/budget", response_model=BudgetResponse)
async def update_budget(
    payload: BudgetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BudgetResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: PUT /transactions/budget — define (ou limpa, com
    `monthly_budget: null`) o teto mensal do usuário autenticado.
    """
    use_case = UpdateBudgetUseCase(SqlAlchemyUserRepository(db))
    monthly_budget_cents = (
        _to_cents(payload.monthly_budget) if payload.monthly_budget is not None else None
    )
    updated_cents = await use_case.execute(
        UpdateBudgetInput(user_id=current_user.id, monthly_budget_cents=monthly_budget_cents)
    )
    await db.commit()
    return BudgetResponse(monthly_budget=_cents_to_decimal(updated_cents))


@router.get("/{public_id}", response_model=TransactionResponse)
async def get_transaction(
    public_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: GET /transactions/{public_id} — detalhe usado no
    pré-preenchimento da edição.
    """
    use_case = GetTransactionUseCase(
        SqlAlchemyTransactionRepository(db), SqlAlchemyCategoryRepository(db)
    )
    try:
        result = await use_case.execute(current_user.id, _parse_transaction_public_id(public_id))
    except TransactionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found") from exc

    return _transaction_response(result)


@router.put("/{public_id}", response_model=TransactionResponse)
async def update_transaction(
    public_id: str,
    payload: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> TransactionResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: PUT /transactions/{public_id} — atualização parcial.
    Desde o build-context-04, também reenfileira a indexação de
    embedding da transação editada.
    """
    use_case = UpdateTransactionUseCase(
        SqlAlchemyTransactionRepository(db), SqlAlchemyCategoryRepository(db), arq_pool
    )
    try:
        result = await use_case.execute(
            UpdateTransactionInput(
                user_id=current_user.id,
                public_id=_parse_transaction_public_id(public_id),
                category_public_id=(
                    _parse_category_public_id(payload.category_id) if payload.category_id else None
                ),
                type=None,
                amount=payload.amount,
                description=payload.description,
                date=payload.date,
                status=PaymentStatus(payload.status) if payload.status else None,
                payment_method=payload.payment_method,
                paid_at=payload.paid_at,
            )
        )
    except TransactionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found") from exc
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc
    except InvalidTransactionAmountError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Amount must be greater than zero"
        ) from exc

    await db.commit()
    return _transaction_response(result)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    public_id: str,
    all_occurrences: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: DELETE /transactions/{public_id} — exclui uma transação.
    `all_occurrences=true` (ignorado silenciosamente numa transação
    avulsa, sem recorrência nem parcelamento) exclui todo o grupo:
    numa transação recorrente, todo o histórico materializado da regra +
    desativa a regra; numa parcela, todas as parcelas da mesma compra
    (`installment_group_id`) — em vez de excluir só a transação/parcela
    clicada.
    """
    use_case = DeleteTransactionUseCase(
        SqlAlchemyTransactionRepository(db), SqlAlchemyRecurrenceRuleRepository(db), arq_pool
    )
    try:
        await use_case.execute(
            DeleteTransactionInput(
                user_id=current_user.id,
                public_id=_parse_transaction_public_id(public_id),
                delete_all_occurrences=all_occurrences,
            )
        )
    except TransactionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found") from exc
    await db.commit()


@router.post("/{public_id}/receipt", response_model=TransactionResponse)
async def upload_receipt(
    public_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: POST /transactions/{public_id}/receipt — upload de
    comprovante (proxy pelo backend, build-context-03 §2.8).
    """
    use_case = UploadReceiptUseCase(
        SqlAlchemyTransactionRepository(db),
        SqlAlchemyCategoryRepository(db),
        storage_client_factory=BackblazeStorageClient,
    )
    content = await file.read()
    try:
        result = await use_case.execute(
            UploadReceiptInput(
                user_id=current_user.id,
                public_id=_parse_transaction_public_id(public_id),
                filename=file.filename or "receipt",
                content_type=file.content_type or "application/octet-stream",
                content=content,
            )
        )
    except TransactionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found") from exc
    except InvalidReceiptFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    await db.commit()
    return _transaction_response(result)


@router.delete("/{public_id}/receipt", response_model=TransactionResponse)
async def delete_receipt(
    public_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: DELETE /transactions/{public_id}/receipt — remove o
    comprovante anexado.
    """
    use_case = DeleteReceiptUseCase(
        SqlAlchemyTransactionRepository(db),
        SqlAlchemyCategoryRepository(db),
        storage_client_factory=BackblazeStorageClient,
    )
    try:
        result = await use_case.execute(
            DeleteReceiptInput(
                user_id=current_user.id, public_id=_parse_transaction_public_id(public_id)
            )
        )
    except TransactionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found") from exc

    await db.commit()
    return _transaction_response(result)
