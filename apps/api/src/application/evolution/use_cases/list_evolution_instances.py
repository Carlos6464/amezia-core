from dataclasses import dataclass

from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.repository import EvolutionInstanceRepository


@dataclass
class ListEvolutionInstancesResult:
    items: list[EvolutionInstance]
    total: int


class ListEvolutionInstancesUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Lista paginada de instâncias Evolution — usada pela tela
    WhatsApp do Admin (build-context-06 §2.3).
    """

    def __init__(self, evolution_instance_repository: EvolutionInstanceRepository) -> None:
        self._repository = evolution_instance_repository

    async def execute(self, page: int, page_size: int) -> ListEvolutionInstancesResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Delega a paginação inteira ao repositório e embrulha
        o resultado na DTO de aplicação.
        """
        items, total = await self._repository.list_paginated(page, page_size)
        return ListEvolutionInstancesResult(items=items, total=total)
