import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal

from src.application.embedding.use_cases.index_transaction_embedding import (
    build_transaction_content,
)
from src.application.shared.ports import JobEnqueuer
from src.application.transaction.dtos import CategorySummary, TransactionWithCategory
from src.domain.category.entities import Category
from src.domain.category.exceptions import CategoryNotFoundError
from src.domain.category.repository import CategoryRepository
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.exceptions import TransactionNotFoundError
from src.domain.transaction.repository import TransactionRepository
from src.domain.transaction.value_objects import Money, PaymentStatus, TransactionType


@dataclass
class UpdateTransactionInput:
    user_id: uuid.UUID
    public_id: PublicId
    category_public_id: PublicId | None = None
    type: TransactionType | None = None
    amount: Decimal | None = None
    description: str | None = None
    date: dt.date | None = None
    status: PaymentStatus | None = None
    payment_method: str | None = None
    paid_at: dt.date | None = None


class UpdateTransactionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Atualização parcial de uma transação existente do próprio
    usuário (RN-01). Revalida a categoria (global ou do usuário) só
    quando `category_public_id` vem preenchido — trocar de categoria não
    é diferente de criar, em termos de validação.
    """

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        category_repository: CategoryRepository,
        job_enqueuer: JobEnqueuer,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._category_repository = category_repository
        self._job_enqueuer = job_enqueuer

    async def execute(self, input_data: UpdateTransactionInput) -> TransactionWithCategory:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Carrega a transação (já escopada por user_id — 404
        para inexistente ou de outro usuário), aplica os campos
        informados e persiste.
        """
        transaction = await self._transaction_repository.get_by_public_id(
            input_data.user_id, input_data.public_id
        )
        if transaction is None:
            raise TransactionNotFoundError(str(input_data.public_id))

        if input_data.category_public_id is not None:
            category = await self._resolve_category(input_data.user_id, input_data.category_public_id)
            transaction.category_id = category.id
        else:
            category = await self._category_repository.get_by_id(transaction.category_id)

        if input_data.type is not None:
            transaction.type = input_data.type
        if input_data.amount is not None:
            transaction.amount = Money.from_decimal(input_data.amount)
        if input_data.description is not None:
            transaction.description = input_data.description
        if input_data.date is not None:
            transaction.date = input_data.date
        if input_data.status is not None:
            transaction.status = input_data.status
        if input_data.payment_method is not None:
            transaction.payment_method = input_data.payment_method
        if input_data.paid_at is not None:
            transaction.paid_at = input_data.paid_at

        updated = await self._transaction_repository.update(transaction)
        content = build_transaction_content(updated, category.name)
        await self._job_enqueuer.enqueue_job(
            "index_transaction_embedding", str(input_data.user_id), updated.id, content
        )
        return TransactionWithCategory(
            transaction=updated, category=CategorySummary.from_entity(category)
        )

    async def _resolve_category(self, user_id: uuid.UUID, category_public_id: PublicId) -> Category:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Mesma validação de posse do CreateTransactionUseCase
        — 404 tanto para categoria inexistente quanto privada de outro
        usuário (RN-01).
        """
        category = await self._category_repository.get_by_public_id(category_public_id)
        if category is None or (not category.is_global and category.user_id != user_id):
            raise CategoryNotFoundError(str(category_public_id))
        return category
