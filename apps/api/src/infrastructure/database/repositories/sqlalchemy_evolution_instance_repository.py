from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.evolution.entities import EvolutionInstance as EvolutionInstanceEntity
from src.domain.evolution.exceptions import DuplicateEvolutionInstanceNameError
from src.domain.evolution.value_objects import ConnectionStatus
from src.domain.shared.value_objects import PublicId
from src.infrastructure.database.models.evolution_instance import (
    EvolutionInstance as EvolutionInstanceModel,
)


class SqlAlchemyEvolutionInstanceRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Implementação concreta de EvolutionInstanceRepository via
    SQLAlchemy async — traduz entre a entidade de domínio EvolutionInstance
    e o model ORM. Cifra/decifra de `phone_number`/`webhook_secret`
    acontece de forma transparente no `EncryptedString` do model, não aqui.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, instance: EvolutionInstanceEntity) -> EvolutionInstanceEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Persiste uma nova instância. Traduz violação do índice
        único de `name` em DuplicateEvolutionInstanceNameError.
        """
        model = self._to_model(instance)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateEvolutionInstanceNameError(instance.name) from exc
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, id: int) -> EvolutionInstanceEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca pela PK interna.
        """
        model = await self._session.get(EvolutionInstanceModel, id)
        return self._to_entity(model) if model else None

    async def get_by_public_id(self, public_id: PublicId) -> EvolutionInstanceEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca pelo public_id (ULID) exposto na API.
        """
        result = await self._session.execute(
            select(EvolutionInstanceModel).where(
                EvolutionInstanceModel.public_id == str(public_id)
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_name(self, name: str) -> EvolutionInstanceEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca pelo nome registrado na Evolution API — usado
        pelo webhook (build-context-06 §2.5) para resolver a instância a
        partir do payload recebido.
        """
        result = await self._session.execute(
            select(EvolutionInstanceModel).where(EvolutionInstanceModel.name == name)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_active(self) -> EvolutionInstanceEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca a instância ativa (`is_active=true`) — MVP1 opera
        com no máximo uma por vez (índice parcial único no banco garante
        isso na escrita).
        """
        result = await self._session.execute(
            select(EvolutionInstanceModel).where(EvolutionInstanceModel.is_active.is_(True))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_paginated(
        self, page: int, page_size: int
    ) -> tuple[list[EvolutionInstanceEntity], int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Lista paginada, mais recentes primeiro — sem filtros
        (a spec não define nenhum para esta listagem).
        """
        count_result = await self._session.execute(
            select(func.count()).select_from(EvolutionInstanceModel)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(EvolutionInstanceModel)
            .order_by(EvolutionInstanceModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_entity(model) for model in result.scalars().all()]
        return items, total

    async def update(self, instance: EvolutionInstanceEntity) -> EvolutionInstanceEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Atualiza todos os campos mutáveis de uma instância
        existente a partir da entidade de domínio. Levanta ValueError se o
        `id` não corresponder a nenhuma linha.
        """
        model = await self._session.get(EvolutionInstanceModel, instance.id)
        if model is None:
            raise ValueError(f"EvolutionInstance {instance.id} not found")
        model.name = instance.name
        model.phone_number = instance.phone_number
        model.status = instance.status.value
        model.qr_code = instance.qr_code
        model.qr_code_expires_at = instance.qr_code_expires_at
        model.webhook_url = instance.webhook_url
        model.webhook_secret = instance.webhook_secret
        model.is_active = instance.is_active
        model.connected_at = instance.connected_at
        model.last_message_at = instance.last_message_at
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateEvolutionInstanceNameError(instance.name) from exc
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, instance: EvolutionInstanceEntity) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Remove a instância do banco. Silenciosamente no-op se
        já não existir.
        """
        model = await self._session.get(EvolutionInstanceModel, instance.id)
        if model is None:
            return
        await self._session.delete(model)
        await self._session.flush()

    def _to_entity(self, model: EvolutionInstanceModel) -> EvolutionInstanceEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Converte o model SQLAlchemy (infraestrutura) na
        entidade de domínio EvolutionInstance.
        """
        return EvolutionInstanceEntity(
            id=model.id,
            public_id=PublicId(model.public_id),
            name=model.name,
            phone_number=model.phone_number,
            status=ConnectionStatus(model.status),
            qr_code=model.qr_code,
            qr_code_expires_at=model.qr_code_expires_at,
            webhook_url=model.webhook_url,
            webhook_secret=model.webhook_secret,
            is_active=model.is_active,
            connected_at=model.connected_at,
            last_message_at=model.last_message_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: EvolutionInstanceEntity) -> EvolutionInstanceModel:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Converte a entidade de domínio EvolutionInstance num
        model SQLAlchemy novo (ainda não persistido) — usado só por
        `create`.
        """
        return EvolutionInstanceModel(
            public_id=str(entity.public_id),
            name=entity.name,
            phone_number=entity.phone_number,
            status=entity.status.value,
            qr_code=entity.qr_code,
            qr_code_expires_at=entity.qr_code_expires_at,
            webhook_url=entity.webhook_url,
            webhook_secret=entity.webhook_secret,
            is_active=entity.is_active,
            connected_at=entity.connected_at,
            last_message_at=entity.last_message_at,
        )
