from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from src.domain.shared.value_objects import PublicId
from src.domain.transaction.entities import RecurrenceRule, Transaction
from src.domain.transaction.value_objects import PaymentStatus, Period, TransactionType


@dataclass
class TransactionFilters:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Filtros aceitos por TransactionRepository.list()/sum_amount().
    `type`/`status`/`period` são aplicados em SQL; `q` (busca textual) só
    pode ser resolvido em memória, porque `description` é criptografado em
    repouso (RN-05) e não é pesquisável por `ILIKE` contra o ciphertext —
    ver build-context-03 §2.5.
    """

    type: TransactionType | None = None
    status: PaymentStatus | None = None
    period: Period | None = None
    q: str | None = None


class TransactionRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Interface de persistência do agregado Transaction —
    implementada em
    infrastructure/database/repositories/transaction_repository.py. O
    domínio depende só deste contrato, nunca de SQLAlchemy.
    """

    async def create(self, transaction: Transaction) -> Transaction: ...

    async def create_many(self, transactions: list[Transaction]) -> list[Transaction]: ...

    async def get_by_public_id(
        self, user_id: uuid.UUID, public_id: PublicId
    ) -> Transaction | None: ...

    async def list(
        self, user_id: uuid.UUID, filters: TransactionFilters, page: int, page_size: int
    ) -> tuple[list[Transaction], int]: ...

    async def sum_amount(self, user_id: uuid.UUID, filters: TransactionFilters) -> int: ...

    async def update(self, transaction: Transaction) -> Transaction: ...

    async def delete(self, user_id: uuid.UUID, public_id: PublicId) -> bool: ...

    async def delete_many(self, user_id: uuid.UUID, public_ids: list[PublicId]) -> int: ...

    async def delete_by_recurrence_rule(
        self, user_id: uuid.UUID, recurrence_rule_id: int
    ) -> int: ...

    async def delete_by_installment_group(
        self, user_id: uuid.UUID, installment_group_id: uuid.UUID
    ) -> int: ...

    async def usage_by_category(self, user_id: uuid.UUID) -> dict[int, tuple[int, int]]: ...

    async def sum_by_category(
        self, user_id: uuid.UUID, filters: TransactionFilters
    ) -> list[tuple[str, int]]: ...

    async def list_distinct_active_user_ids_since(self, since: datetime) -> set[uuid.UUID]:
        """
        Usuários distintos com pelo menos 1 transação criada desde
        `since` — uma das 3 fontes de "usuário ativo" do DAU/MAU do
        Admin (build-context-11 §2.2). Filtra por `created_at` (quando
        a ação aconteceu), nunca por `date` (data do lançamento, que o
        usuário pode retroagir/adiantar livremente).
        """
        ...


class RecurrenceRuleRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Interface de persistência de RecurrenceRule —
    implementada em
    infrastructure/database/repositories/recurrence_rule_repository.py.
    `list_due` não é escopado por `user_id`: é usado só pelo job ARQ cron
    (generate_recurring_transactions), que varre regras de todos os
    usuários — o único ponto do sistema fora do módulo Admin que
    legitimamente cruza usuários, porque é infraestrutura de job, não uma
    rota HTTP.
    """

    async def create(self, rule: RecurrenceRule) -> RecurrenceRule: ...

    async def get_by_public_id(
        self, user_id: uuid.UUID, public_id: PublicId
    ) -> RecurrenceRule | None: ...

    async def get_by_id(self, id: int) -> RecurrenceRule | None: ...

    async def list_active_for_user(self, user_id: uuid.UUID) -> list[RecurrenceRule]: ...

    async def list_due(self, as_of: date) -> list[RecurrenceRule]: ...

    async def update(self, rule: RecurrenceRule) -> RecurrenceRule: ...
