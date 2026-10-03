from dataclasses import dataclass

from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.evolution.value_objects import ConnectionStatus


@dataclass
class BotInfo:
    phone_number: str | None
    is_available: bool


class GetBotInfoUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Informação pública (não-admin) do bot WhatsApp — só o
    número e se está disponível pra conversar, pro onboarding mostrar um
    link `wa.me/<número>` sem expor nada da instância Evolution além
    disso (público_id, webhook_secret etc. continuam só no Admin).
    """

    def __init__(self, evolution_instance_repository: EvolutionInstanceRepository) -> None:
        self._evolution_instance_repository = evolution_instance_repository

    async def execute(self) -> BotInfo:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Busca a instância ativa (mesmo critério já usado pelo
        job de mensagem de boas-vindas) — sem instância ativa ou sem
        número ainda vinculado, devolve `is_available=False`.
        """
        instance = await self._evolution_instance_repository.get_active()
        if instance is None or instance.phone_number is None:
            return BotInfo(phone_number=None, is_available=False)

        return BotInfo(
            phone_number=instance.phone_number,
            is_available=instance.status == ConnectionStatus.CONNECTED,
        )
