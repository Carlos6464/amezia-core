from datetime import UTC, datetime

from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.exceptions import EvolutionInstanceNotFoundError
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.evolution.value_objects import ConnectionStatus
from src.domain.shared.value_objects import PublicId
from src.infrastructure.whatsapp.evolution_client import EvolutionApiClient


class SyncEvolutionInstanceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Refresh manual — consulta o estado atual na Evolution API
    e atualiza status/phone_number/connected_at localmente (build-context-06
    §2.3), complementar aos eventos de webhook (que também atualizam os
    mesmos campos, de forma assíncrona).
    """

    def __init__(
        self,
        evolution_instance_repository: EvolutionInstanceRepository,
        evolution_api_client: EvolutionApiClient,
    ) -> None:
        self._repository = evolution_instance_repository
        self._client = evolution_api_client

    async def execute(self, public_id: PublicId) -> EvolutionInstance:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Consulta o estado real na Evolution API e sincroniza
        status/phone_number/connected_at/qr_code localmente — 404 via
        EvolutionInstanceNotFoundError se a instância não existir.
        """
        instance = await self._repository.get_by_public_id(public_id)
        if instance is None:
            raise EvolutionInstanceNotFoundError(str(public_id))

        raw_state, phone_number = await self._client.get_connection_state(instance.name)
        new_status = ConnectionStatus.from_raw(raw_state)

        if new_status == ConnectionStatus.CONNECTED and instance.status != ConnectionStatus.CONNECTED:
            instance.connected_at = datetime.now(UTC)
        if new_status != ConnectionStatus.CONNECTED:
            instance.connected_at = None

        instance.status = new_status
        instance.phone_number = phone_number
        if new_status != ConnectionStatus.CONNECTING:
            instance.qr_code = None
            instance.qr_code_expires_at = None

        return await self._repository.update(instance)
