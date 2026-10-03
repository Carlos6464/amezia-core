from __future__ import annotations

import uuid
from typing import Protocol

from src.domain.reports.value_objects import (
    CategoryDistributionItem,
    FinancialSummary,
    MonthlyEvolutionPoint,
    MonthlyPaidPendingPoint,
    Page,
    PaymentMethodDistributionItem,
    PeriodRange,
    TransactionSummary,
)
from src.domain.transaction.value_objects import Period


class ReportsRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Interface de persistência de leitura/agregação dos
    Relatórios — implementada em
    infrastructure/database/repositories/sqlalchemy_reports_repository.py.
    Repositório próprio em vez de estender `TransactionRepository`
    (build-context-05 §2.3, Interface Segregation): Transações não
    precisa carregar métodos de agregação que só Relatórios consome.
    Todo método recebe `user_id` explicitamente e filtra por ele (RN-01)
    — nunca delega esse filtro para a camada de cima. `category_id`, aqui
    e nos use cases, é sempre o id interno (`int`) já resolvido a partir
    do `public_id` recebido do cliente — mesmo padrão de
    `CreateTransactionUseCase._resolve_category`. Sem filtro de tipo
    (produto é expense-only, pedido do usuário em 2026-08-14) — toda
    transação já é despesa.
    """

    async def get_financial_summary(
        self, user_id: uuid.UUID, period: PeriodRange
    ) -> FinancialSummary: ...

    async def get_monthly_evolution(
        self, user_id: uuid.UUID, reference_period: Period, months: int
    ) -> list[MonthlyEvolutionPoint]: ...

    async def get_category_distribution(
        self, user_id: uuid.UUID, period: PeriodRange
    ) -> list[CategoryDistributionItem]: ...

    async def get_payment_method_distribution(
        self, user_id: uuid.UUID, period: PeriodRange
    ) -> list[PaymentMethodDistributionItem]:
        """
        Distribuição por tipo de pagamento do período (2026-09-15,
        fora de qualquer build-context) — diferente de
        `get_category_distribution`, não pode ser um `GROUP BY` em SQL
        (`Transaction.payment_method` é criptografado, RN-05); a
        implementação concreta agrega em memória, depois de decriptar.
        """
        ...

    async def get_monthly_paid_pending(
        self, user_id: uuid.UUID, reference_period: Period, months: int
    ) -> list[MonthlyPaidPendingPoint]:
        """
        Série mensal pago x pendente (2026-09-15, fora de qualquer
        build-context) — mesmo recorte de `get_monthly_evolution`
        (`months` meses corridos até `reference_period`, inclusive),
        quebrado por `PaymentStatus` em vez de um total único.
        """
        ...

    async def get_transactions_page(
        self,
        user_id: uuid.UUID,
        period: PeriodRange,
        category_id: int | None,
        page: int,
        page_size: int,
        payment_method: str | None = None,
    ) -> Page[TransactionSummary]:
        """
        `payment_method` (2026-09-15, fora de qualquer build-context) é
        opcional e, quando informado, filtra em memória — a coluna é
        criptografada (RN-05), não dá pra `WHERE payment_method = ...`
        em SQL. Alimenta o modal "despesas por tipo de pagamento" do
        Dashboard, mesmo endpoint que já filtra por categoria.
        """
        ...

    async def get_transactions_for_export(
        self,
        user_id: uuid.UUID,
        period: PeriodRange,
        category_id: int | None,
    ) -> list[TransactionSummary]: ...
