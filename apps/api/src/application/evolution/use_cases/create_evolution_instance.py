import logging
import secrets
from dataclasses import dataclass

from src.application.evolution.use_cases.sync_evolution_instance import (
    SyncEvolutionInstanceUseCase,
)
from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.exceptions import (
    DuplicateEvolutionInstanceNameError,
    EvolutionInstanceAlreadyExistsError,
)
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.infrastructure.whatsapp.evolution_client import EvolutionApiClient

logger = logging.getLogger(__name__)

_WEBHOOK_SECRET_BYTES = 32


@dataclass
class CreateEvolutionInstanceInput:
    name: str
    webhook_url: str


class CreateEvolutionInstanceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Registra uma nova instância — cria na Evolution API real
    primeiro (nome + webhook), só persiste localmente se as duas chamadas
    remotas tiverem sucesso, para não deixar um registro órfão local sem
    contrapartida na Evolution API.
    """

    def __init__(
        self,
        evolution_instance_repository: EvolutionInstanceRepository,
        evolution_api_client: EvolutionApiClient,
        sync_evolution_instance_use_case: SyncEvolutionInstanceUseCase,
    ) -> None:
        self._repository = evolution_instance_repository
        self._client = evolution_api_client
        self._sync_use_case = sync_evolution_instance_use_case

    async def execute(self, data: CreateEvolutionInstanceInput) -> EvolutionInstance:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Valida nome único, gera `webhook_secret` (RN-05), cria
        a instância + configura o webhook na Evolution API e persiste o
        registro local. Se a instância já existir do lado da Evolution
        (`EvolutionInstanceAlreadyExistsError`, ex.: criada direto no
        painel dela antes de ser registrada aqui) — **vincula** em vez
        de falhar: continua para `set_webhook` normalmente (o webhook
        deste projeto ainda precisa ser configurado nela) e, ao final,
        sincroniza o estado real (status/número/conexão) via
        `SyncEvolutionInstanceUseCase`, sem o qual a instância nasceria
        marcada como desconectada mesmo já estando pareada. Portado do
        projeto irmão (`/home/adriano/Documentos/projetos/Amezia`),
        2026-08-16.
        """
        existing = await self._repository.get_by_name(data.name)
        if existing is not None:
            raise DuplicateEvolutionInstanceNameError(data.name)

        instance = EvolutionInstance(
            name=data.name,
            webhook_url=data.webhook_url,
            webhook_secret=secrets.token_urlsafe(_WEBHOOK_SECRET_BYTES),
        )

        try:
            await self._client.create_instance(data.name)
        except EvolutionInstanceAlreadyExistsError:
            logger.info(
                "Evolution instance '%s' already existed remotely — linking instead of failing",
                data.name,
            )

        await self._client.set_webhook(data.name, instance.webhook_callback_url)

        created = await self._repository.create(instance)

        try:
            return await self._sync_use_case.execute(created.public_id)
        except Exception:
            logger.warning(
                "Post-creation sync failed for Evolution instance '%s'", data.name, exc_info=True
            )
            return created
