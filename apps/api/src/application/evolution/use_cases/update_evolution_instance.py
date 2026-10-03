from dataclasses import dataclass

from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.exceptions import EvolutionInstanceNotFoundError
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.shared.value_objects import PublicId
from src.infrastructure.whatsapp.evolution_client import EvolutionApiClient


@dataclass
class UpdateEvolutionInstanceInput:
    public_id: PublicId
    name: str | None = None
    webhook_url: str | None = None
    is_active: bool | None = None


class UpdateEvolutionInstanceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Atualização parcial de name/webhook_url/is_active
    (build-context-06 §2.3). MVP1 opera com uma instância ativa por vez
    (§2.2) — ativar esta desativa qualquer outra que estivesse ativa,
    além do índice parcial único no banco (segunda linha de defesa).
    """

    def __init__(
        self,
        evolution_instance_repository: EvolutionInstanceRepository,
        evolution_api_client: EvolutionApiClient,
    ) -> None:
        self._repository = evolution_instance_repository
        self._client = evolution_api_client

    async def execute(self, data: UpdateEvolutionInstanceInput) -> EvolutionInstance:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Aplica os campos informados, reconfigura o webhook na
        Evolution API quando `webhook_url` muda, e desativa qualquer
        outra instância ativa quando esta é marcada `is_active=True`.
        """
        instance = await self._repository.get_by_public_id(data.public_id)
        if instance is None:
            raise EvolutionInstanceNotFoundError(str(data.public_id))

        if data.name is not None:
            instance.name = data.name

        webhook_url_changed = (
            data.webhook_url is not None and data.webhook_url != instance.webhook_url
        )
        if data.webhook_url is not None:
            instance.webhook_url = data.webhook_url

        if data.is_active is not None and data.is_active and not instance.is_active:
            currently_active = await self._repository.get_active()
            if currently_active is not None and currently_active.id != instance.id:
                currently_active.is_active = False
                await self._repository.update(currently_active)

        if data.is_active is not None:
            instance.is_active = data.is_active

        if webhook_url_changed:
            await self._client.set_webhook(instance.name, instance.webhook_callback_url)

        return await self._repository.update(instance)
