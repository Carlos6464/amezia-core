from datetime import UTC, datetime, timedelta

from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.evolution.value_objects import ConnectionStatus


class ApplyQrCodeUpdateUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Efeito do evento de webhook `QRCODE_UPDATED`
    (build-context-06 §2.5) — atualiza qr_code/qr_code_expires_at,
    chamado só pelo job ARQ `qrcode_updated`. Um QR novo sempre indica
    pareamento em andamento (`connecting`), mesmo que o status local
    ainda estivesse diferente.
    """

    def __init__(
        self, evolution_instance_repository: EvolutionInstanceRepository, qr_code_ttl_seconds: int
    ) -> None:
        self._repository = evolution_instance_repository
        self._qr_code_ttl_seconds = qr_code_ttl_seconds

    async def execute(self, instance_id: int, qr_code: str) -> EvolutionInstance | None:
        instance = await self._repository.get_by_id(instance_id)
        if instance is None:
            return None

        instance.qr_code = qr_code
        instance.qr_code_expires_at = datetime.now(UTC) + timedelta(
            seconds=self._qr_code_ttl_seconds
        )
        instance.status = ConnectionStatus.CONNECTING
        return await self._repository.update(instance)
