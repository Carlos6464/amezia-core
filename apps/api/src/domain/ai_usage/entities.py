import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.domain.conversation.value_objects import AiProvider

__all__ = ["AiFeature", "AiProvider", "AiUsageEvent"]


class AiFeature(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Ponto do produto que gerou uma chamada de IA
    (build-context-10 §2.2). Só `AGENT_CHAT`/`REPORT_NARRATIVE` contam
    pro limite mensal de plano (`CheckAiUsageLimitUseCase`) — os outros
    dois só alimentam custo/observabilidade do admin.
    """

    AGENT_CHAT = "agent_chat"
    REPORT_NARRATIVE = "report_narrative"
    BOT_EXPENSE_PARSING = "bot_expense_parsing"
    BOT_AUDIO_TRANSCRIPTION = "bot_audio_transcription"


@dataclass
class AiUsageEvent:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Log unificado de uma chamada de IA já concluída
    (build-context-10 §2.2) — gravado por `RecordAiUsageUseCase` para
    QUALQUER chamada de IA do produto, mesmo as que não contam pra
    limite de plano. `estimated_cost_micros` é calculado uma única vez
    no momento do registro (`pricing.py`) e nunca recalculado depois —
    preserva o custo histórico real mesmo que a tabela de preço mude
    no futuro. Guardado em **micros de BRL** (1 BRL = 1_000_000 micros,
    1 centavo = 10_000 micros), não em centavos — o custo real de uma
    única chamada de IA é uma fração de centavo (achado real, 2026-09-11:
    um chat curto custa ~R$0,001), então arredondar pro centavo mais
    próximo *por evento* zerava o valor antes mesmo de somar; o
    arredondamento pra centavo só acontece uma vez, na borda HTTP
    (`presentation/api/v1/admin/schemas.py`), depois de agregado.
    `AiProvider` é o mesmo enum já usado por `ConversationMessage.
    provider_used` (build-context-04) — reaproveitado aqui em vez de
    duplicado, é o mesmo conceito (Gemini/Grok).
    """

    user_id: uuid.UUID
    feature: AiFeature
    provider: AiProvider
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_micros: int
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
