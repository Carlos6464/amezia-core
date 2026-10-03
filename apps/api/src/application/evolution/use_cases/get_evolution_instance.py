from src.domain.evolution.entities import EvolutionInstance
from src.domain.evolution.exceptions import EvolutionInstanceNotFoundError
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.shared.value_objects import PublicId


class GetEvolutionInstanceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Detalhe de uma instância. As estatísticas de volume de
    mensagens (`messages_today`/`messages_this_month`/`active_users_this_month`,
    build-context-06 §2.3) dependem da tabela `processed_bot_messages`,
    escopo do build-context-07 (ainda não construído) — omitidas aqui de
    propósito, não um esquecimento. Plugar quando o 07 existir.
    """

    def __init__(self, evolution_instance_repository: EvolutionInstanceRepository) -> None:
        self._repository = evolution_instance_repository

    async def execute(self, public_id: PublicId) -> EvolutionInstance:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca a instância pelo public_id — 404 via
        EvolutionInstanceNotFoundError se não existir.
        """
        instance = await self._repository.get_by_public_id(public_id)
        if instance is None:
            raise EvolutionInstanceNotFoundError(str(public_id))
        return instance
