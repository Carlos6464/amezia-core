"""rename ai_usage_events estimated_cost_cents to estimated_cost_micros

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-09-11 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4b5c6d7e8f9'
down_revision: str | Sequence[str] | None = 'f3a4b5c6d7e8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mesma tabela de preço de src/domain/ai_usage/pricing.py, em 2026-09-11 —
# duplicada aqui só porque a migration não pode importar código da aplicação
# (Alembic roda isolado do resto do app). Usada só pra recalcular os poucos
# eventos já gravados com o bug do arredondamento cedo demais (ver downgrade
# nota abaixo: eventos de par provider/model desconhecido ficam com 0, igual
# ao comportamento de `resolve_cost_micros`).
_USD_TO_BRL_RATE = 5.4
_PRICING = {
    ("gemini", "gemini-2.5-flash"): (30, 250),
    ("grok", "grok-4"): (300, 1500),
}


def upgrade() -> None:
    """Upgrade schema.

    Renomeia `estimated_cost_cents` para `estimated_cost_micros`
    (1 BRL = 1_000_000 micros) — o custo real de uma única chamada de
    IA é uma fração de centavo, e arredondar pro centavo mais próximo
    *por evento* (comportamento antigo) zerava o valor antes mesmo de
    agregar (achado real, 2026-09-11: custo estimado sempre em R$0,00
    no painel do admin apesar de uso real registrado). O arredondamento
    final pra centavo passa a acontecer só na borda HTTP
    (`presentation/api/v1/admin/schemas.py`).

    A coluna renomeada mantém o valor antigo (0 em todas as linhas
    existentes até aqui, já que o bug zerava todo evento individual) —
    o UPDATE abaixo recalcula o valor correto em micros pros eventos já
    gravados, usando a mesma tabela de preço de `pricing.py`, pra o
    painel do admin já refletir o custo histórico real assim que a
    migration roda, sem esperar novo tráfego de IA.
    """
    op.alter_column(
        "ai_usage_events", "estimated_cost_cents", new_column_name="estimated_cost_micros"
    )

    connection = op.get_bind()
    for (provider, model), (input_price, output_price) in _PRICING.items():
        connection.execute(
            sa.text(
                """
                UPDATE ai_usage_events
                SET estimated_cost_micros = ROUND(
                    (input_tokens * CAST(:input_price AS numeric) + output_tokens * CAST(:output_price AS numeric))
                    * CAST(:rate AS numeric) * 10000 / 1000000.0
                )
                WHERE provider = :provider AND model = :model
                """
            ),
            {
                "input_price": input_price,
                "output_price": output_price,
                "rate": _USD_TO_BRL_RATE,
                "provider": provider,
                "model": model,
            },
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "ai_usage_events", "estimated_cost_micros", new_column_name="estimated_cost_cents"
    )
