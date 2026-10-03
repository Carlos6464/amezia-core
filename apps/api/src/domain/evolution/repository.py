from typing import Protocol

from src.domain.evolution.entities import EvolutionInstance
from src.domain.shared.value_objects import PublicId


class EvolutionInstanceRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Interface de persistência do agregado EvolutionInstance —
    implementada em
    infrastructure/database/repositories/sqlalchemy_evolution_instance_repository.py.
    O domínio depende só deste contrato, nunca de SQLAlchemy.
    """

    async def create(self, instance: EvolutionInstance) -> EvolutionInstance: ...

    async def get_by_id(self, id: int) -> EvolutionInstance | None: ...

    async def get_by_public_id(self, public_id: PublicId) -> EvolutionInstance | None: ...

    async def get_by_name(self, name: str) -> EvolutionInstance | None: ...

    async def get_active(self) -> EvolutionInstance | None: ...

    async def list_paginated(
        self, page: int, page_size: int
    ) -> tuple[list[EvolutionInstance], int]: ...

    async def update(self, instance: EvolutionInstance) -> EvolutionInstance: ...

    async def delete(self, instance: EvolutionInstance) -> None: ...
