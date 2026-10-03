from datetime import UTC, datetime

from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.evolution.value_objects import ConnectionStatus


class ApplyConnectionUpdateUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Efeito do evento de webhook `CONNECTION_UPDATE`
    (build-context-06 §2.5) — atualiza status/phone_number/connected_at
    a partir do payload da Evolution API, chamado só pelo job ARQ
    `connection_update`, nunca de forma síncrona na requisição do
    webhook (RN-07).
    """

    def __init__(self, evolution_instance_repository: EvolutionInstanceRepository) -> None:
        self._repository = evolution_instance_repository

    async def execute(
        self, instance_id: int, raw_state: str, phone_number: str | None
    ) -> EvolutionInstance | None:
        instance = await self._repository.get_by_id(instance_id)
        if instance is None:
            return None

        new_status = ConnectionStatus.from_raw(raw_state)
        if new_status == ConnectionStatus.CONNECTED and instance.status != ConnectionStatus.CONNECTED:
            instance.connected_at = datetime.now(UTC)
        if new_status != ConnectionStatus.CONNECTED:
            instance.connected_at = None

        instance.status = new_status
        if phone_number is not None:
            instance.phone_number = phone_number
        if new_status != ConnectionStatus.CONNECTING:
            instance.qr_code = None
            instance.qr_code_expires_at = None

        return await self._repository.update(instance)
