from datetime import UTC, datetime, timedelta

from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.exceptions import EvolutionInstanceNotFoundError
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.evolution.value_objects import ConnectionStatus
from src.domain.shared.value_objects import PublicId
from src.infrastructure.whatsapp.evolution_client import EvolutionApiClient


class ConnectEvolutionInstanceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Inicia o pareamento — chama a Evolution API, grava
    `qr_code`/`qr_code_expires_at` e move `status` para `connecting`
    (build-context-06 §2.3). O QR também chega por evento de webhook
    (`QRCODE_UPDATED`), mas esta chamada síncrona é o que dispara a
    exibição inicial na tela.
    """

    def __init__(
        self,
        evolution_instance_repository: EvolutionInstanceRepository,
        evolution_api_client: EvolutionApiClient,
        qr_code_ttl_seconds: int,
    ) -> None:
        self._repository = evolution_instance_repository
        self._client = evolution_api_client
        self._qr_code_ttl_seconds = qr_code_ttl_seconds

    async def execute(self, public_id: PublicId) -> EvolutionInstance:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Pede o QR à Evolution API e grava qr_code/
        qr_code_expires_at/status=connecting — 404 via
        EvolutionInstanceNotFoundError se a instância não existir.
        """
        instance = await self._repository.get_by_public_id(public_id)
        if instance is None:
            raise EvolutionInstanceNotFoundError(str(public_id))

        qr_code = await self._client.connect_instance(instance.name)
        instance.qr_code = qr_code
        instance.qr_code_expires_at = (
            datetime.now(UTC) + timedelta(seconds=self._qr_code_ttl_seconds)
            if qr_code is not None
            else None
        )
        instance.status = ConnectionStatus.CONNECTING
        return await self._repository.update(instance)
