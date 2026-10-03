import logging
import uuid
from dataclasses import dataclass

from src.domain.ai_usage.entities import AiFeature, AiProvider, AiUsageEvent
from src.domain.ai_usage.pricing import PRICING_PER_MILLION_TOKENS, resolve_cost_micros
from src.domain.ai_usage.repository import AiUsageRepository

logger = logging.getLogger(__name__)


@dataclass
class RecordAiUsageInput:
    user_id: uuid.UUID
    feature: AiFeature
    provider: AiProvider
    model: str
    input_tokens: int
    output_tokens: int


class RecordAiUsageUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Chamado por QUALQUER caller de IA do produto, ao fim de
    uma chamada bem-sucedida (build-context-10 §2.1/T6) — os 4 pontos
    de entrada de hoje são `GenerateAiResponseUseCase` (chat),
    `GenerateAiNarrativeUseCase` (narrativa), `RegisterExpenseViaBotUseCase`
    (parsing de despesa via bot) e `HandleExpenseStateUseCase` (transcrição
    de áudio). Nenhum caminho de chamada de IA fica fora do log, mesmo os
    que não contam pra limite de plano (§2.2) — o log também alimenta
    custo/admin.
    """

    def __init__(self, ai_usage_repository: AiUsageRepository) -> None:
        self._ai_usage_repository = ai_usage_repository

    async def execute(self, input_data: RecordAiUsageInput) -> AiUsageEvent:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Calcula o custo estimado (`pricing.py`) e grava o
        evento — loga um warning (não falha) quando o par
        (provider, model) ainda não está cadastrado na tabela de preço,
        já que o registro de uso é observabilidade, nunca pode derrubar
        a feature de IA que já rodou com sucesso.
        """
        if (input_data.provider, input_data.model) not in PRICING_PER_MILLION_TOKENS:
            logger.warning(
                "No pricing registered for provider=%s model=%s — recording estimated_cost_micros=0",
                input_data.provider.value,
                input_data.model,
            )

        cost_micros = resolve_cost_micros(
            input_data.provider, input_data.model, input_data.input_tokens, input_data.output_tokens
        )
        event = AiUsageEvent(
            user_id=input_data.user_id,
            feature=input_data.feature,
            provider=input_data.provider,
            model=input_data.model,
            input_tokens=input_data.input_tokens,
            output_tokens=input_data.output_tokens,
            estimated_cost_micros=cost_micros,
        )
        return await self._ai_usage_repository.record(event)
