from dataclasses import dataclass

from src.domain.ai_usage.entities import AiProvider

# Cotação USD -> BRL aproximada, fixa em código (não é uma tabela de câmbio ao
# vivo) — os providers de IA cobram em USD, mas o resto do produto (planos,
# pagamentos) trabalha em centavos de BRL (RN de moeda única do PRD). Este
# valor é só para a estimativa de custo do admin (§2.4 do build-context-10 já
# deixa explícito na UI que não é saldo real de conta) — revisar
# periodicamente, não é atualizado automaticamente.
_USD_TO_BRL_RATE = 5.4


@dataclass(frozen=True)
class PriceRow:
    """Preço em centavos de USD por 1 milhão de tokens — convertido pra BRL só no cálculo final (`resolve_cost_micros`)."""

    input_usd_cents_per_million: int
    output_usd_cents_per_million: int


# Valores públicos de tabela dos providers (Google AI/xAI), em setembro de
# 2026 — sujeitos a mudança, revisar quando os providers reajustarem preço.
# Só os modelos hoje em produção (build-context-10 §2.3: `model` é VARCHAR,
# não enum, pra modelo novo não exigir migration).
PRICING_PER_MILLION_TOKENS: dict[tuple[AiProvider, str], PriceRow] = {
    (AiProvider.GEMINI, "gemini-2.5-flash"): PriceRow(
        input_usd_cents_per_million=30, output_usd_cents_per_million=250
    ),
    (AiProvider.GROK, "grok-4"): PriceRow(
        input_usd_cents_per_million=300, output_usd_cents_per_million=1500
    ),
}


def resolve_cost_micros(
    provider: AiProvider, model: str, input_tokens: int, output_tokens: int
) -> int:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Calcula o custo estimado em micros de BRL (1 BRL =
    1_000_000 micros, 1 centavo = 10_000 micros) de uma chamada de IA
    (build-context-10 §2.4) — chamado uma única vez, no momento do
    registro (`RecordAiUsageUseCase`), nunca recalculado depois. Usa
    micros em vez de centavos porque o custo real de uma única chamada
    é uma fração de centavo (achado real, 2026-09-11: um chat curto
    custa ~R$0,001) — arredondar pro centavo aqui, por evento, zerava o
    valor antes mesmo de agregar; o arredondamento final pra centavo
    acontece só na borda HTTP (`presentation/api/v1/admin/schemas.py`).
    Modelo desconhecido (ainda não cadastrado em
    `PRICING_PER_MILLION_TOKENS`) devolve custo 0 em vez de falhar a
    chamada de IA por causa de preço ausente — o registro de uso é
    observabilidade, não pode derrubar a feature.
    """
    price = PRICING_PER_MILLION_TOKENS.get((provider, model))
    if price is None:
        return 0

    usd_cents = (
        input_tokens * price.input_usd_cents_per_million
        + output_tokens * price.output_usd_cents_per_million
    ) / 1_000_000
    return round(usd_cents * _USD_TO_BRL_RATE * 10_000)
