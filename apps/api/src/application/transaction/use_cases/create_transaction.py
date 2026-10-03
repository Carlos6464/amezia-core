import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.application.embedding.use_cases.index_transaction_embedding import (
    build_transaction_content,
)
from src.application.shared.ports import JobEnqueuer
from src.application.transaction.dtos import CategorySummary, TransactionWithCategory
from src.application.transaction.use_cases.create_recurring_transaction import (
    CreateRecurringTransactionInput,
    CreateRecurringTransactionUseCase,
)
from src.domain.category.entities import Category
from src.domain.category.exceptions import CategoryNotFoundError
from src.domain.category.repository import CategoryRepository
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.entities import Transaction
from src.domain.transaction.repository import TransactionRepository
from src.domain.transaction.value_objects import (
    Money,
    PaymentStatus,
    RecurrenceFrequency,
    TransactionType,
    add_months,
)

MAX_INSTALLMENTS = 60


@dataclass
class InstallmentInput:
    total: int


@dataclass
class RecurrenceInput:
    frequency: RecurrenceFrequency
    end_date: date | None


@dataclass
class CreateTransactionInput:
    user_id: uuid.UUID
    category_public_id: PublicId
    type: TransactionType
    amount: Decimal
    description: str
    date: date
    status: PaymentStatus = PaymentStatus.PAID
    payment_method: str | None = None
    installment: InstallmentInput | None = None
    recurrence: RecurrenceInput | None = None


class CreateTransactionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Cria uma transação, ramificando em 3 caminhos conforme o
    corpo da requisição (build-context-03 §2.3/§2.7): simples (padrão),
    parcelada (`installment` presente, N linhas geradas de uma vez via
    `create_many` — tem fim conhecido) ou recorrente (`recurrence`
    presente, delega a CreateRecurringTransactionUseCase — não tem fim
    conhecido, não pré-gera nada além da 1ª ocorrência). Valida em
    qualquer caminho que a categoria pertence ao usuário ou é global.
    """

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        category_repository: CategoryRepository,
        recurring_transaction_use_case: CreateRecurringTransactionUseCase,
        job_enqueuer: JobEnqueuer,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._category_repository = category_repository
        self._recurring_transaction_use_case = recurring_transaction_use_case
        self._job_enqueuer = job_enqueuer

    async def _enqueue_indexing(self, user_id: uuid.UUID, transaction: Transaction, category_name: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Enfileira o job `index_transaction_embedding`
        (build-context-04 §2.4/T11) — chamado nos 3 caminhos de criação
        (simples, parcelada, recorrente).
        """
        content = build_transaction_content(transaction, category_name)
        await self._job_enqueuer.enqueue_job(
            "index_transaction_embedding", str(user_id), transaction.id, content
        )

    async def execute(self, input_data: CreateTransactionInput) -> TransactionWithCategory:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Ponto de entrada único — resolve a categoria uma vez e
        despacha para o caminho certo (simples/parcelada/recorrente).
        `installment` e `recurrence` são mutuamente exclusivos na borda
        HTTP (schemas.py); aqui, `recurrence` tem prioridade se, por
        algum motivo, os dois vierem preenchidos.
        """
        category = await self._resolve_category(input_data.user_id, input_data.category_public_id)

        if input_data.recurrence is not None:
            result = await self._recurring_transaction_use_case.execute(
                CreateRecurringTransactionInput(
                    user_id=input_data.user_id,
                    category=category,
                    type=input_data.type,
                    amount=Money.from_decimal(input_data.amount),
                    description=input_data.description,
                    status=input_data.status,
                    start_date=input_data.date,
                    frequency=input_data.recurrence.frequency,
                    end_date=input_data.recurrence.end_date,
                )
            )
            await self._enqueue_indexing(input_data.user_id, result.transaction, category.name)
            return result

        amount = Money.from_decimal(input_data.amount)

        if input_data.installment is not None and input_data.installment.total > 1:
            return await self._create_installments(input_data, category, amount)

        transaction = Transaction(
            user_id=input_data.user_id,
            category_id=category.id,
            type=input_data.type,
            amount=amount,
            description=input_data.description,
            date=input_data.date,
            status=input_data.status,
            payment_method=input_data.payment_method,
        )
        created = await self._transaction_repository.create(transaction)
        await self._enqueue_indexing(input_data.user_id, created, category.name)
        return TransactionWithCategory(
            transaction=created, category=CategorySummary.from_entity(category)
        )

    async def _resolve_category(
        self, user_id: uuid.UUID, category_public_id: PublicId
    ) -> Category:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Resolve o `public_id` de categoria recebido do
        cliente para a entidade real, validando que é global ou
        pertence ao usuário autenticado — CategoryNotFoundError (404)
        tanto para categoria inexistente quanto para categoria privada
        de outro usuário (RN-01, não revela existência).
        """
        category = await self._category_repository.get_by_public_id(category_public_id)
        if category is None or (not category.is_global and category.user_id != user_id):
            raise CategoryNotFoundError(str(category_public_id))
        return category

    async def _create_installments(
        self, input_data: CreateTransactionInput, category: Category, amount: Money
    ) -> TransactionWithCategory:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Gera as N parcelas de uma vez (build-context-03 §2.7)
        — mesmo `installment_group_id` (novo UUID), `amount` igual em
        cada parcela (valor por parcela, não o total dividido), datas
        mensais a partir de `date` (mesmo dia do mês, caindo no último
        dia quando o mês de destino não tiver esse dia). Só a 1ª parcela
        recebe o `status` escolhido no formulário (pode nascer paga, com
        comprovante anexado em seguida pelo cliente) — as demais nascem
        sempre `PENDING`, mesmo que o usuário tenha marcado "pago" na
        criação: parcelas futuras são compromissos ainda não honrados,
        cada uma só deve virar "paga" quando o usuário efetivamente
        pagar aquele mês específico, editando a transação dela (ajuste
        pedido pelo usuário, 2026-08-09). Retorna a primeira parcela
        como representante da criação — a listagem mostra as demais.
        """
        group_id = uuid.uuid4()
        total = input_data.installment.total
        installments = [
            Transaction(
                user_id=input_data.user_id,
                category_id=category.id,
                type=input_data.type,
                amount=amount,
                description=input_data.description,
                date=add_months(input_data.date, number - 1),
                status=input_data.status if number == 1 else PaymentStatus.PENDING,
                payment_method=input_data.payment_method,
                installment_group_id=group_id,
                installment_number=number,
                installment_total=total,
            )
            for number in range(1, total + 1)
        ]
        created = await self._transaction_repository.create_many(installments)
        for installment in created:
            await self._enqueue_indexing(input_data.user_id, installment, category.name)
        return TransactionWithCategory(
            transaction=created[0], category=CategorySummary.from_entity(category)
        )
