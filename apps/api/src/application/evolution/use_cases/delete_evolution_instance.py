from src.domain.evolution.exceptions import EvolutionInstanceNotFoundError
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.shared.value_objects import PublicId
from src.infrastructure.whatsapp.evolution_client import EvolutionApiClient


class DeleteEvolutionInstanceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Remove a instância da Evolution API e, em seguida, do
    banco local (build-context-06 §2.3).
    """

    def __init__(
        self,
        evolution_instance_repository: EvolutionInstanceRepository,
        evolution_api_client: EvolutionApiClient,
    ) -> None:
        self._repository = evolution_instance_repository
        self._client = evolution_api_client

    async def execute(self, public_id: PublicId) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Remove primeiro na Evolution API, só então localmente
        — 404 via EvolutionInstanceNotFoundError se a instância não
        existir.
        """
        instance = await self._repository.get_by_public_id(public_id)
        if instance is None:
            raise EvolutionInstanceNotFoundError(str(public_id))
        await self._client.delete_instance(instance.name)
        await self._repository.delete(instance)
