from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.exceptions import EvolutionInstanceNotFoundError
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.evolution.value_objects import ConnectionStatus
from src.domain.shared.value_objects import PublicId
from src.infrastructure.whatsapp.evolution_client import EvolutionApiClient


class DisconnectEvolutionInstanceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Logout da sessão pareada na Evolution API e marca
    `status = disconnected` localmente (build-context-06 §2.3) — a
    instância continua registrada, só perde a sessão pareada.
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
        Descrição: Faz logout na Evolution API e limpa status/telefone/
        QR localmente — 404 via EvolutionInstanceNotFoundError se a
        instância não existir.
        """
        instance = await self._repository.get_by_public_id(public_id)
        if instance is None:
            raise EvolutionInstanceNotFoundError(str(public_id))

        await self._client.logout_instance(instance.name)
        instance.status = ConnectionStatus.DISCONNECTED
        instance.phone_number = None
        instance.connected_at = None
        instance.qr_code = None
        instance.qr_code_expires_at = None
        return await self._repository.update(instance)
