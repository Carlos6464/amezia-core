import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.shared.value_objects import PublicId
from src.domain.transaction.entities import RecurrenceRule as RecurrenceRuleEntity
from src.domain.transaction.value_objects import Money, RecurrenceFrequency, TransactionType
from src.infrastructure.database.models.recurrence_rule import (
    RecurrenceRule as RecurrenceRuleModel,
)


class SqlAlchemyRecurrenceRuleRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Implementação concreta de RecurrenceRuleRepository via
    SQLAlchemy async — traduz entre a entidade de domínio RecurrenceRule
    e o model ORM.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, rule: RecurrenceRuleEntity) -> RecurrenceRuleEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Persiste uma nova regra de recorrência.
        """
        model = self._to_model(rule)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_public_id(
        self, user_id: uuid.UUID, public_id: PublicId
    ) -> RecurrenceRuleEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Busca uma regra por public_id, escopada por user_id
        (RN-01) — usada por CancelRecurrenceUseCase.
        """
        result = await self._session.execute(
            select(RecurrenceRuleModel).where(
                RecurrenceRuleModel.user_id == user_id,
                RecurrenceRuleModel.public_id == str(public_id),
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, id: int) -> RecurrenceRuleEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-10
        Descrição: Busca uma regra pelo id interno (sem escopo de
        usuário) — usada por DeleteTransactionUseCase, que só tem o
        `recurrence_rule_id` carregado na própria Transaction (não o
        public_id da regra) e já validou a posse via a transação.
        """
        model = await self._session.get(RecurrenceRuleModel, id)
        return self._to_entity(model) if model else None

    async def list_active_for_user(self, user_id: uuid.UUID) -> list[RecurrenceRuleEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Lista as regras ativas do usuário autenticado, usada
        por ListRecurrencesUseCase.
        """
        result = await self._session.execute(
            select(RecurrenceRuleModel)
            .where(RecurrenceRuleModel.user_id == user_id, RecurrenceRuleModel.active.is_(True))
            .order_by(RecurrenceRuleModel.next_occurrence_date)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_due(self, as_of: date) -> list[RecurrenceRuleEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Regras ativas de todos os usuários cuja próxima
        ocorrência já chegou — usado só pelo job ARQ cron
        (generate_recurring_transactions), não por nenhuma rota HTTP.
        """
        result = await self._session.execute(
            select(RecurrenceRuleModel).where(
                RecurrenceRuleModel.active.is_(True),
                RecurrenceRuleModel.next_occurrence_date <= as_of,
            )
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def update(self, rule: RecurrenceRuleEntity) -> RecurrenceRuleEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Atualiza os campos mutáveis de uma regra — usado tanto
        para cancelar (active=False) quanto para avançar
        next_occurrence_date após o job materializar uma ocorrência.
        """
        model = await self._session.get(RecurrenceRuleModel, rule.id)
        if model is None:
            raise ValueError(f"RecurrenceRule {rule.id} not found")
        model.category_id = rule.category_id
        model.type = rule.type.value
        model.amount_cents = rule.amount.amount_cents
        model.currency = rule.amount.currency
        model.description = rule.description
        model.frequency = rule.frequency.value
        model.start_date = rule.start_date
        model.end_date = rule.end_date
        model.next_occurrence_date = rule.next_occurrence_date
        model.active = rule.active
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    def _to_entity(self, model: RecurrenceRuleModel) -> RecurrenceRuleEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte o model SQLAlchemy na entidade de domínio
        RecurrenceRule.
        """
        return RecurrenceRuleEntity(
            id=model.id,
            public_id=PublicId(model.public_id),
            user_id=model.user_id,
            category_id=model.category_id,
            type=TransactionType(model.type),
            amount=Money(amount_cents=model.amount_cents, currency=model.currency),
            description=model.description,
            frequency=RecurrenceFrequency(model.frequency),
            start_date=model.start_date,
            end_date=model.end_date,
            next_occurrence_date=model.next_occurrence_date,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: RecurrenceRuleEntity) -> RecurrenceRuleModel:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte a entidade de domínio RecurrenceRule num
        model SQLAlchemy novo (ainda não persistido) — usado só por
        `create`.
        """
        return RecurrenceRuleModel(
            public_id=str(entity.public_id),
            user_id=entity.user_id,
            category_id=entity.category_id,
            type=entity.type.value,
            amount_cents=entity.amount.amount_cents,
            currency=entity.amount.currency,
            description=entity.description,
            frequency=entity.frequency.value,
            start_date=entity.start_date,
            end_date=entity.end_date,
            next_occurrence_date=entity.next_occurrence_date,
            active=entity.active,
        )
