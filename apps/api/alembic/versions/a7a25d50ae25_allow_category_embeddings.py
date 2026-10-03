"""allow category embeddings

Revision ID: a7a25d50ae25
Revises: b5b603b3d5f9
Create Date: 2026-09-09 09:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7a25d50ae25'
down_revision: str | Sequence[str] | None = 'b5b603b3d5f9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Postgres >= 12 permite ALTER TYPE ... ADD VALUE dentro de uma transação, desde que o
    # valor novo não seja usado na mesma transação (build-context-12 §3.3) — categoria
    # (global e privada) passa a ter embedding na mesma tabela `embeddings` do RAG.
    op.execute("ALTER TYPE embedding_source_type ADD VALUE IF NOT EXISTS 'category'")

    # Categoria global (`categories.user_id IS NULL`) não tem dono — a linha de embedding
    # dela em `embeddings` também precisa aceitar `user_id IS NULL`. `transaction`/
    # `conversation_message` continuam sempre preenchendo (nunca são globais).
    op.alter_column("embeddings", "user_id", existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres não suporta remover um valor de enum diretamente (exigiria recriar o tipo
    # inteiro e todas as colunas que o usam) — linhas com source_type='category' precisam
    # ser removidas manualmente antes de reverter esta migration, se for o caso.
    op.alter_column("embeddings", "user_id", existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=False)
