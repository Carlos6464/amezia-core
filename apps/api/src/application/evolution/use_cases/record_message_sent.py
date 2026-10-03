from datetime import UTC, datetime

from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.repository import EvolutionInstanceRepository


class RecordMessageSentUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Efeito do evento de webhook `SEND_MESSAGE`
    (build-context-06 §2.5) — atualiza `last_message_at`, chamado só
    pelo job ARQ `send_message`.
    """

    def __init__(self, evolution_instance_repository: EvolutionInstanceRepository) -> None:
        self._repository = evolution_instance_repository

    async def execute(self, instance_id: int) -> EvolutionInstance | None:
        instance = await self._repository.get_by_id(instance_id)
        if instance is None:
            return None
        instance.last_message_at = datetime.now(UTC)
        return await self._repository.update(instance)
