from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.domain.reports.value_objects import (
    CategoryDistributionItem,
    CategorySummary,
    FinancialSummary,
    MonthlyEvolutionPoint,
    MonthlyPaidPendingPoint,
    Page,
    PaymentMethodDistributionItem,
    PeriodRange,
    TransactionSummary,
)
from src.domain.transaction.value_objects import Money, PaymentStatus, Period, add_months
from src.infrastructure.database.models.category import Category as CategoryModel
from src.infrastructure.database.models.transaction import Transaction as TransactionModel

NOT_INFORMED_PAYMENT_METHOD = "not_informed"
"""Chave usada em `get_payment_method_distribution` pra agrupar transações sem `payment_method` preenchido — mesmo valor que `presentation/api/v1/reports/schemas.py` espera."""


class SqlAlchemyReportsRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Implementação concreta de `ReportsRepository` — consulta
    diretamente `TransactionModel`/`CategoryModel` (já definidos pelos
    módulos 02/03) via SQLAlchemy async, sem depender de `domain/`/
    `application/` desses módulos (build-context-05 §2.3). Toda query é
    escopada por `user_id` explicitamente (RN-01). Sem filtro de tipo:
    produto é expense-only (pedido do usuário, 2026-08-14) — toda
    transação já é despesa, `TransactionModel.type` nunca é lido aqui.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _conditions(
        self,
        user_id: uuid.UUID,
        period: PeriodRange,
        category_id: int | None = None,
        status: str | None = None,
    ) -> list[ColumnElement[bool]]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Condições SQL comuns a todas as queries de Relatórios
        — período (intervalo de dias derivado de `PeriodRange.date_range()`,
        não só um mês/ano como `TransactionFilters` de Transações) e,
        quando informada, categoria. `status` (2026-09-15) é opcional e
        só usado por `get_monthly_paid_pending` — `PaymentStatus` é enum
        de verdade, não criptografado (diferente de `payment_method`),
        então filtrar por ele continua puro SQL.
        """
        start, end = period.date_range()
        conditions: list[ColumnElement[bool]] = [
            TransactionModel.user_id == user_id,
            TransactionModel.date.between(start, end),
        ]
        if category_id is not None:
            conditions.append(TransactionModel.category_id == category_id)
        if status is not None:
            conditions.append(TransactionModel.status == status)
        return conditions

    async def get_financial_summary(
        self, user_id: uuid.UUID, period: PeriodRange
    ) -> FinancialSummary:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Total, contagem, maior categoria e maior transação do
        período — 3 queries agregadas, mais baratas que carregar todas
        as linhas do período em memória.
        """
        conditions = self._conditions(user_id, period)
        total_expense = await self._sum(conditions)

        count_result = await self._session.execute(
            select(func.count()).select_from(TransactionModel).where(*conditions)
        )
        transaction_count = count_result.scalar_one()

        top_category = await self._top_category(conditions)
        biggest_transaction = await self._biggest_transaction(conditions)

        return FinancialSummary(
            period=period,
            total_expense=total_expense,
            transaction_count=transaction_count,
            top_category=top_category,
            biggest_transaction=biggest_transaction,
        )

    async def _sum(self, conditions: list[ColumnElement[bool]]) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Soma em centavos do conjunto filtrado — `coalesce`
        garante `0` (não `None`) quando não há nenhuma linha.
        """
        result = await self._session.execute(
            select(func.coalesce(func.sum(TransactionModel.amount_cents), 0))
            .select_from(TransactionModel)
            .where(*conditions)
        )
        return result.scalar_one()

    async def _top_category(
        self, conditions: list[ColumnElement[bool]]
    ) -> CategorySummary | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Categoria de maior soma dentro das condições dadas —
        `percentage` relativo à soma total das mesmas condições.
        """
        total_expr = func.coalesce(func.sum(TransactionModel.amount_cents), 0)
        result = await self._session.execute(
            select(CategoryModel.public_id, CategoryModel.name, total_expr)
            .join(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .where(*conditions)
            .group_by(CategoryModel.id, CategoryModel.public_id, CategoryModel.name)
            .order_by(total_expr.desc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        public_id, name, total = row
        overall = await self._sum(conditions)
        percentage = (total / overall * 100) if overall else 0.0
        return CategorySummary(
            category_id=public_id, category_name=name, total=total, percentage=percentage
        )

    async def _biggest_transaction(
        self, conditions: list[ColumnElement[bool]]
    ) -> TransactionSummary | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Transação de maior valor dentro das condições dadas —
        usada como "maior despesa" no resumo/stats-strip.
        """
        result = await self._session.execute(
            select(TransactionModel, CategoryModel.public_id, CategoryModel.name)
            .join(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .where(*conditions)
            .order_by(TransactionModel.amount_cents.desc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        model, category_public_id, category_name = row
        return self._to_transaction_summary(model, category_public_id, category_name)

    async def get_monthly_evolution(
        self, user_id: uuid.UUID, reference_period: Period, months: int
    ) -> list[MonthlyEvolutionPoint]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Um ponto por mês, dos `months` meses corridos até
        `reference_period` (inclusive), em ordem cronológica crescente —
        usado pelo line-chart do Dashboard (6 meses) e pelo contexto da
        narrativa IA (meses do intervalo selecionado).
        """
        reference_date = reference_period.date_range()[0]
        points: list[MonthlyEvolutionPoint] = []
        for offset in range(months - 1, -1, -1):
            month_date = add_months(reference_date, -offset)
            month_period = Period(year=month_date.year, month=month_date.month)
            month_range = PeriodRange(start=month_period, end=month_period)
            expense = await self._sum(self._conditions(user_id, month_range))
            points.append(MonthlyEvolutionPoint(period=month_period, total_expense=expense))
        return points

    async def get_monthly_paid_pending(
        self, user_id: uuid.UUID, reference_period: Period, months: int
    ) -> list[MonthlyPaidPendingPoint]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Mesmo recorte de `get_monthly_evolution` (`months`
        meses corridos até `reference_period`, inclusive, ordem
        cronológica crescente), mas somando `status=paid` e
        `status=pending` separadamente por mês — alimenta o gráfico de
        barra dupla "Pago x Pendente" (pedido direto do usuário, fora
        de qualquer build-context). Duas somas SQL por mês em vez de
        uma — `status` não é criptografado, então continua barato.
        """
        reference_date = reference_period.date_range()[0]
        points: list[MonthlyPaidPendingPoint] = []
        for offset in range(months - 1, -1, -1):
            month_date = add_months(reference_date, -offset)
            month_period = Period(year=month_date.year, month=month_date.month)
            month_range = PeriodRange(start=month_period, end=month_period)
            paid = await self._sum(
                self._conditions(user_id, month_range, status=PaymentStatus.PAID.value)
            )
            pending = await self._sum(
                self._conditions(user_id, month_range, status=PaymentStatus.PENDING.value)
            )
            points.append(
                MonthlyPaidPendingPoint(period=month_period, total_paid=paid, total_pending=pending)
            )
        return points

    async def get_category_distribution(
        self, user_id: uuid.UUID, period: PeriodRange
    ) -> list[CategoryDistributionItem]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Distribuição por categoria do período, ordenada por
        total desc.
        """
        conditions = self._conditions(user_id, period)
        total_expr = func.coalesce(func.sum(TransactionModel.amount_cents), 0)
        result = await self._session.execute(
            select(
                CategoryModel.public_id,
                CategoryModel.name,
                CategoryModel.color,
                total_expr,
            )
            .join(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .where(*conditions)
            .group_by(CategoryModel.id, CategoryModel.public_id, CategoryModel.name, CategoryModel.color)
            .order_by(total_expr.desc())
        )
        rows = result.all()
        overall = sum(row[3] for row in rows) or 1
        return [
            CategoryDistributionItem(
                category_id=public_id,
                category_name=name,
                color=color,
                total=total,
                percentage=(total / overall * 100),
            )
            for public_id, name, color, total in rows
        ]

    async def get_payment_method_distribution(
        self, user_id: uuid.UUID, period: PeriodRange
    ) -> list[PaymentMethodDistributionItem]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Distribuição por tipo de pagamento do período,
        ordenada por total desc (pedido direto do usuário, fora de
        qualquer build-context) — diferente de `get_category_distribution`,
        não dá pra usar `GROUP BY` em SQL aqui: `payment_method` é
        criptografado (`EncryptedString`, RN-05), então a agregação
        acontece em memória, depois que o ORM já decriptou cada linha
        de forma transparente. Sem `join`/paginação nenhuma — só as 2
        colunas necessárias (`payment_method`, `amount_cents`) das
        transações do período. Transação sem `payment_method` (`None`
        ou string vazia) entra na fatia `NOT_INFORMED_PAYMENT_METHOD`.
        """
        conditions = self._conditions(user_id, period)
        result = await self._session.execute(
            select(TransactionModel.payment_method, TransactionModel.amount_cents).where(*conditions)
        )
        totals_by_method: dict[str, int] = {}
        for payment_method, amount_cents in result.all():
            key = payment_method or NOT_INFORMED_PAYMENT_METHOD
            totals_by_method[key] = totals_by_method.get(key, 0) + amount_cents

        overall = sum(totals_by_method.values()) or 1
        items = [
            PaymentMethodDistributionItem(
                payment_method=method,
                total=total,
                percentage=(total / overall * 100),
            )
            for method, total in totals_by_method.items()
        ]
        items.sort(key=lambda item: item.total, reverse=True)
        return items

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
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Tabela paginada de transações do intervalo — usada
        pela tela de Reports e pelo preview de 5 mais recentes do
        Dashboard (`page_size=5`). Sem `payment_method`, é paginação
        SQL de verdade (`OFFSET`/`LIMIT`), como sempre foi. Com
        `payment_method` (2026-09-15, fora de qualquer build-context —
        modal "despesas por tipo de pagamento" do Dashboard), cai num
        caminho separado: busca todas as linhas do período/categoria,
        filtra por `payment_method` em memória (coluna criptografada,
        RN-05 — mesma razão de `_search_candidates` em Transações) e só
        então pagina o resultado já filtrado, em Python.
        """
        conditions = self._conditions(user_id, period, category_id)

        if payment_method is not None:
            return await self._transactions_page_by_payment_method(
                conditions, payment_method, page, page_size
            )

        count_result = await self._session.execute(
            select(func.count()).select_from(TransactionModel).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(TransactionModel, CategoryModel.public_id, CategoryModel.name)
            .join(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .where(*conditions)
            .order_by(TransactionModel.date.desc(), TransactionModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            self._to_transaction_summary(model, category_public_id, category_name)
            for model, category_public_id, category_name in result.all()
        ]
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return Page(items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)

    async def _transactions_page_by_payment_method(
        self,
        conditions: list[ColumnElement[bool]],
        payment_method: str,
        page: int,
        page_size: int,
    ) -> Page[TransactionSummary]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Carrega todas as linhas que batem as condições SQL
        (período/categoria), filtra por `payment_method` já decriptado
        em memória, e pagina a lista filtrada em Python — o preço de
        não poder paginar em SQL quando o filtro depende de um campo
        criptografado. `payment_method == NOT_INFORMED_PAYMENT_METHOD`
        é tratado à parte: esse valor é só a **chave de agrupamento**
        que `get_payment_method_distribution` usa pra exibir a fatia
        "Não informado" — o dado real da transação continua `None`
        (nunca é gravado como a string `"not_informed"`), então o
        filtro precisa casar por "vazio", não por igualdade literal com
        a chave (bug real: o modal de "Não informado" no Dashboard
        vinha sempre vazio até esta correção).
        """
        result = await self._session.execute(
            select(TransactionModel, CategoryModel.public_id, CategoryModel.name)
            .join(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .where(*conditions)
            .order_by(TransactionModel.date.desc(), TransactionModel.id.desc())
        )
        if payment_method == NOT_INFORMED_PAYMENT_METHOD:
            matching = [row for row in result.all() if not row[0].payment_method]
        else:
            matching = [row for row in result.all() if row[0].payment_method == payment_method]
        total = len(matching)
        start = (page - 1) * page_size
        page_rows = matching[start : start + page_size]
        items = [
            self._to_transaction_summary(model, category_public_id, category_name)
            for model, category_public_id, category_name in page_rows
        ]
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return Page(items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)

    async def get_transactions_for_export(
        self,
        user_id: uuid.UUID,
        period: PeriodRange,
        category_id: int | None,
    ) -> list[TransactionSummary]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Todas as transações do intervalo, sem paginação — o
        arquivo CSV exportado cobre o filtro inteiro (build-context-05
        §2.6).
        """
        conditions = self._conditions(user_id, period, category_id)
        result = await self._session.execute(
            select(TransactionModel, CategoryModel.public_id, CategoryModel.name)
            .join(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .where(*conditions)
            .order_by(TransactionModel.date.desc(), TransactionModel.id.desc())
        )
        return [
            self._to_transaction_summary(model, category_public_id, category_name)
            for model, category_public_id, category_name in result.all()
        ]

    def _to_transaction_summary(
        self, model: TransactionModel, category_public_id: str, category_name: str
    ) -> TransactionSummary:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Converte o model SQLAlchemy (já com `description`
        descriptografada de forma transparente pelo `EncryptedString`,
        RN-05) na VO de leitura `TransactionSummary`.
        """
        return TransactionSummary(
            public_id=model.public_id,
            occurred_at=model.date,
            description=model.description,
            category_id=category_public_id,
            category_name=category_name,
            amount=Money(amount_cents=model.amount_cents, currency=model.currency),
        )
