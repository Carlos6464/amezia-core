from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.domain.shared.value_objects import PublicId
from src.domain.transaction.entities import Transaction as TransactionEntity
from src.domain.transaction.repository import TransactionFilters
from src.domain.transaction.value_objects import Money, PaymentStatus, TransactionType
from src.infrastructure.database.models.category import Category as CategoryModel
from src.infrastructure.database.models.transaction import Transaction as TransactionModel

# `payment_method` é `str | None` livre no domínio (sem enum/migration,
# `domain/transaction/entities.py`), mas na prática só chega um destes 8
# valores — é a única lista que o combobox do frontend oferece
# (`payment-method-select.component.ts::PAYMENT_METHODS`, sem opção de
# texto livre). Duplicado aqui (2026-09-15, pedido direto do usuário, fora
# de qualquer build-context) só para a busca por texto também bater com o
# rótulo em português que o usuário vê na tela, não só o código em inglês
# salvo no banco (ex.: buscar "cartão" deve achar `credit_card`) — o
# backend não tem i18n de verdade, isso é uma exceção pontual e pequena,
# não um sistema de tradução novo.
_PAYMENT_METHOD_SEARCH_LABELS: dict[str, str] = {
    "pix": "pix",
    "credit_card": "cartão de crédito",
    "debit_card": "cartão de débito",
    "cash": "dinheiro",
    "bank_transfer": "transferência bancária",
    "boleto": "boleto",
    "check": "cheque",
    "other": "outro",
}


def _payment_method_matches(payment_method: str | None, term: str) -> bool:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: `term` já vem em minúsculas — compara com o valor bruto
    salvo (`payment_method`) e com o rótulo em português correspondente
    (`_PAYMENT_METHOD_SEARCH_LABELS`), pra "pix"/"cartão"/"dinheiro"
    digitado na busca encontrar a transação mesmo o banco guardando só
    o código em inglês.
    """
    if not payment_method:
        return False
    if term in payment_method.lower():
        return True
    label = _PAYMENT_METHOD_SEARCH_LABELS.get(payment_method)
    return label is not None and term in label


class SqlAlchemyTransactionRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Implementação concreta de TransactionRepository via
    SQLAlchemy async — traduz entre a entidade de domínio Transaction e
    o model ORM. Toda operação escopada a um usuário recebe `user_id`
    explicitamente e filtra `WHERE user_id = :user_id` — nunca delega
    esse filtro para a camada de cima (RN-01).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, transaction: TransactionEntity) -> TransactionEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Persiste uma nova transação simples (não parcelada,
        não recorrente).
        """
        model = self._to_model(transaction)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def create_many(self, transactions: list[TransactionEntity]) -> list[TransactionEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Insere várias transações numa única operação —
        usado para gerar todas as parcelas de uma compra parcelada de
        uma vez (build-context-03 §2.7), em vez de N chamadas a `create`.
        """
        models = [self._to_model(transaction) for transaction in transactions]
        self._session.add_all(models)
        await self._session.flush()
        for model in models:
            await self._session.refresh(model)
        return [self._to_entity(model) for model in models]

    async def get_by_public_id(
        self, user_id: uuid.UUID, public_id: PublicId
    ) -> TransactionEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Busca uma transação por public_id, já escopada por
        user_id — transação de outro usuário simplesmente "não existe"
        do ponto de vista de quem pediu (RN-01, evita enumeração de IDs).
        """
        result = await self._session.execute(
            select(TransactionModel).where(
                TransactionModel.user_id == user_id,
                TransactionModel.public_id == str(public_id),
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    def _base_conditions(
        self, user_id: uuid.UUID, filters: TransactionFilters
    ) -> list[ColumnElement[bool]]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Filtros que dependem só de colunas em texto plano —
        aplicáveis em SQL. `q` (busca textual) fica de fora daqui de
        propósito, porque `description` é criptografado (RN-05) e só
        pode ser filtrado depois de decriptado em memória — ver
        `_search_candidates`.
        """
        conditions: list[ColumnElement[bool]] = [TransactionModel.user_id == user_id]
        if filters.type is not None:
            conditions.append(TransactionModel.type == filters.type.value)
        if filters.status is not None:
            conditions.append(TransactionModel.status == filters.status.value)
        if filters.period is not None:
            start, end = filters.period.date_range()
            conditions.append(TransactionModel.date.between(start, end))
        return conditions

    async def _search_candidates(
        self, user_id: uuid.UUID, filters: TransactionFilters
    ) -> list[TransactionModel]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Mecânica da busca em memória (build-context-03 §2.5):
        busca as linhas candidatas após os filtros SQL de
        user/type/status/period, sem LIMIT/OFFSET ainda, com join em
        `categories` só para ler o nome (não criptografado). A
        decriptação de `description`/`payment_method` já é transparente
        via `EncryptedString` no momento em que o SQLAlchemy monta o
        objeto Python — não é uma chamada manual a `decrypt()`. Filtra
        em memória contra `description` decriptado, nome de categoria e
        tipo de pagamento (case-insensitive, 2026-09-15 — ver
        `_payment_method_matches`) porque não é possível `WHERE
        description ILIKE ...` contra o ciphertext em repouso.
        """
        conditions = self._base_conditions(user_id, filters)
        result = await self._session.execute(
            select(TransactionModel)
            .join(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .where(*conditions)
            .order_by(TransactionModel.date.desc(), TransactionModel.id.desc())
        )
        models = list(result.scalars().all())
        if not filters.q:
            return models

        term = filters.q.lower()
        category_names = await self._category_names_by_id(
            {model.category_id for model in models}
        )
        return [
            model
            for model in models
            if term in model.description.lower()
            or term in category_names.get(model.category_id, "").lower()
            or _payment_method_matches(model.payment_method, term)
        ]

    async def _category_names_by_id(self, category_ids: set[int]) -> dict[int, str]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Lookup em lote do nome das categorias envolvidas — usado
        pela busca textual (`_search_candidates`) para casar contra o nome
        da categoria sem uma query por linha.
        """
        if not category_ids:
            return {}
        result = await self._session.execute(
            select(CategoryModel.id, CategoryModel.name).where(CategoryModel.id.in_(category_ids))
        )
        return dict(result.all())

    async def list(
        self, user_id: uuid.UUID, filters: TransactionFilters, page: int, page_size: int
    ) -> tuple[list[TransactionEntity], int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Lista paginada. Sem `q`: filtro e paginação inteiros em
        SQL (LIMIT/OFFSET + COUNT). Com `q`: pagina em memória sobre o
        resultado já filtrado por `_search_candidates`, porque o filtro
        final só existe depois da decriptação (build-context-03 §2.5).
        """
        if filters.q:
            candidates = await self._search_candidates(user_id, filters)
            total = len(candidates)
            start = (page - 1) * page_size
            page_models = candidates[start : start + page_size]
            return [self._to_entity(model) for model in page_models], total

        conditions = self._base_conditions(user_id, filters)
        count_result = await self._session.execute(
            select(func.count()).select_from(TransactionModel).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(TransactionModel)
            .where(*conditions)
            .order_by(TransactionModel.date.desc(), TransactionModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_entity(model) for model in result.scalars().all()]
        return items, total

    async def sum_amount(self, user_id: uuid.UUID, filters: TransactionFilters) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Soma em centavos do conjunto filtrado completo (não só
        a página) — alimenta `summary.total_amount`. Sem `q`: `SUM` em
        SQL. Com `q`: soma sobre os mesmos candidatos já filtrados por
        `_search_candidates`, evitando duplicar a lógica de match.
        """
        if filters.q:
            candidates = await self._search_candidates(user_id, filters)
            return sum(model.amount_cents for model in candidates)

        conditions = self._base_conditions(user_id, filters)
        result = await self._session.execute(
            select(func.coalesce(func.sum(TransactionModel.amount_cents), 0))
            .select_from(TransactionModel)
            .where(*conditions)
        )
        return result.scalar_one()

    async def update(self, transaction: TransactionEntity) -> TransactionEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Atualiza os campos mutáveis de uma transação já
        existente — a entidade sempre vem de um `get_by_public_id`
        anterior, então `id` já está preenchido.
        """
        model = await self._session.get(TransactionModel, transaction.id)
        if model is None:
            raise ValueError(f"Transaction {transaction.id} not found")
        model.category_id = transaction.category_id
        model.type = transaction.type.value
        model.amount_cents = transaction.amount.amount_cents
        model.currency = transaction.amount.currency
        model.description = transaction.description
        model.date = transaction.date
        model.status = transaction.status.value
        model.payment_method = transaction.payment_method
        model.receipt_key = transaction.receipt_key
        model.paid_at = transaction.paid_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, user_id: uuid.UUID, public_id: PublicId) -> bool:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Exclui uma transação escopada por user_id. Retorna
        False (não levanta exceção) quando não encontra nada — quem
        chama decide se isso é um TransactionNotFoundError.
        """
        result = await self._session.execute(
            select(TransactionModel).where(
                TransactionModel.user_id == user_id,
                TransactionModel.public_id == str(public_id),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def delete_many(self, user_id: uuid.UUID, public_ids: list[PublicId]) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Exclusão em lote, idempotente por design — public_ids
        que não existem ou não pertencem ao usuário simplesmente não
        aparecem no resultado da query, sem gerar erro.
        """
        if not public_ids:
            return 0
        ids = [str(public_id) for public_id in public_ids]
        result = await self._session.execute(
            select(TransactionModel).where(
                TransactionModel.user_id == user_id,
                TransactionModel.public_id.in_(ids),
            )
        )
        models = list(result.scalars().all())
        for model in models:
            await self._session.delete(model)
        if models:
            await self._session.flush()
        return len(models)

    async def delete_by_recurrence_rule(self, user_id: uuid.UUID, recurrence_rule_id: int) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-10
        Descrição: Exclui todas as ocorrências já materializadas de uma
        regra de recorrência — usado quando o usuário escolhe "excluir
        todas" em vez de excluir só a transação individual (a regra em
        si é desativada à parte, por quem chama, mesmo padrão de
        CancelRecurrenceUseCase). Escopado por user_id mesmo a regra já
        tendo sido validada como do usuário — defesa em profundidade.
        """
        result = await self._session.execute(
            select(TransactionModel).where(
                TransactionModel.user_id == user_id,
                TransactionModel.recurrence_rule_id == recurrence_rule_id,
            )
        )
        models = list(result.scalars().all())
        for model in models:
            await self._session.delete(model)
        if models:
            await self._session.flush()
        return len(models)

    async def delete_by_installment_group(
        self, user_id: uuid.UUID, installment_group_id: uuid.UUID
    ) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Exclui todas as parcelas de uma mesma compra parcelada
        (mesmo `installment_group_id`) — usado quando o usuário escolhe
        "excluir todas" numa transação parcelada, em vez de excluir só a
        parcela individual. Diferente de `delete_by_recurrence_rule`, não
        existe regra/gerador associado a desativar: todas as parcelas já
        foram materializadas de uma vez na criação
        (`CreateTransactionUseCase._create_installments`), então excluir
        o grupo inteiro é a operação completa, sem efeito colateral.
        Escopado por user_id (RN-01), defesa em profundidade.
        """
        result = await self._session.execute(
            select(TransactionModel).where(
                TransactionModel.user_id == user_id,
                TransactionModel.installment_group_id == installment_group_id,
            )
        )
        models = list(result.scalars().all())
        for model in models:
            await self._session.delete(model)
        if models:
            await self._session.flush()
        return len(models)

    async def usage_by_category(self, user_id: uuid.UUID) -> dict[int, tuple[int, int]]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Quantidade de transações e soma em centavos por
        categoria do usuário — alimenta as colunas "Uso"/"Movimentado" e
        o card "Mais usada" de Categorias (build-context-02, ficou como
        placeholder "—" até Transações existir pra agregar esses dados —
        Observação 2 do build-context-02). Só categorias com pelo menos
        1 transação aparecem no dict; quem chama trata a ausência de uma
        chave como zero, não como erro.
        """
        result = await self._session.execute(
            select(
                TransactionModel.category_id,
                func.count(),
                func.coalesce(func.sum(TransactionModel.amount_cents), 0),
            )
            .where(TransactionModel.user_id == user_id)
            .group_by(TransactionModel.category_id)
        )
        return {row[0]: (row[1], row[2]) for row in result.all()}

    async def sum_by_category(
        self, user_id: uuid.UUID, filters: TransactionFilters
    ) -> list[tuple[str, int]]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-12
        Descrição: Soma em centavos agrupada por categoria, respeitando
        os mesmos filtros de tipo/status/período de `sum_amount` — usada
        pelo snapshot financeiro determinístico do Agente de IA
        (`_build_financial_snapshot`) para responder "em qual categoria
        eu mais gastei", que RAG sozinho não resolve bem (mesma classe
        de bug do total mensal: pergunta de agregação, não de trecho
        específico). Ordenado do maior gasto pro menor; só categorias
        com pelo menos 1 transação no filtro aparecem.
        """
        conditions = self._base_conditions(user_id, filters)
        total_expr = func.coalesce(func.sum(TransactionModel.amount_cents), 0)
        result = await self._session.execute(
            select(CategoryModel.name, total_expr)
            .join(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .where(*conditions)
            .group_by(CategoryModel.id, CategoryModel.name)
            .order_by(total_expr.desc())
        )
        return [(row[0], row[1]) for row in result.all()]

    async def list_distinct_active_user_ids_since(self, since: datetime) -> set[uuid.UUID]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Usuários distintos com pelo menos 1 transação criada
        desde `since` — uma das 3 fontes de DAU/MAU do Admin
        (build-context-11 §2.2).
        """
        result = await self._session.execute(
            select(TransactionModel.user_id.distinct()).where(
                TransactionModel.created_at >= since
            )
        )
        return set(result.scalars().all())

    def _to_entity(self, model: TransactionModel) -> TransactionEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte o model SQLAlchemy na entidade de domínio
        Transaction — fronteira entre as duas camadas.
        """
        return TransactionEntity(
            id=model.id,
            public_id=PublicId(model.public_id),
            user_id=model.user_id,
            category_id=model.category_id,
            type=TransactionType(model.type),
            amount=Money(amount_cents=model.amount_cents, currency=model.currency),
            description=model.description,
            date=model.date,
            status=PaymentStatus(model.status),
            payment_method=model.payment_method,
            receipt_key=model.receipt_key,
            paid_at=model.paid_at,
            installment_group_id=model.installment_group_id,
            installment_number=model.installment_number,
            installment_total=model.installment_total,
            recurrence_rule_id=model.recurrence_rule_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: TransactionEntity) -> TransactionModel:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte a entidade de domínio Transaction num model
        SQLAlchemy novo (ainda não persistido) — usado por `create` e
        `create_many`.
        """
        return TransactionModel(
            public_id=str(entity.public_id),
            user_id=entity.user_id,
            category_id=entity.category_id,
            type=entity.type.value,
            amount_cents=entity.amount.amount_cents,
            currency=entity.amount.currency,
            description=entity.description,
            date=entity.date,
            status=entity.status.value,
            payment_method=entity.payment_method,
            receipt_key=entity.receipt_key,
            installment_group_id=entity.installment_group_id,
            installment_number=entity.installment_number,
            installment_total=entity.installment_total,
            recurrence_rule_id=entity.recurrence_rule_id,
        )
