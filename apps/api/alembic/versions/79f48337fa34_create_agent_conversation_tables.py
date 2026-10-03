"""create agent conversation tables

Revision ID: 79f48337fa34
Revises: 2f8a6b1c9d3e
Create Date: 2026-08-11 08:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '79f48337fa34'
down_revision: str | Sequence[str] | None = '2f8a6b1c9d3e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

conversation_channel_enum = postgresql.ENUM("web", "whatsapp", name="conversation_channel")
message_role_enum = postgresql.ENUM("user", "assistant", name="message_role")
ai_provider_enum = postgresql.ENUM("gemini", "grok", name="ai_provider")
embedding_source_type_enum = postgresql.ENUM(
    "transaction", "conversation_message", name="embedding_source_type"
)

EMBEDDING_DIMENSION = 768


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    conversation_channel_enum.create(bind, checkfirst=True)
    message_role_enum.create(bind, checkfirst=True)
    ai_provider_enum.create(bind, checkfirst=True)
    embedding_source_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Ciphertext AES (RN-05) via EncryptedString — sem length fixo, mesmo padrão de users.phone.
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        # FK para conversation_messages.id adicionada abaixo, depois que a tabela existir
        # (referência circular: conversations <-> conversation_messages).
        sa.Column("summarized_until_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "channel",
            postgresql.ENUM("web", "whatsapp", name="conversation_channel", create_type=False),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ux_conversations_public_id", "conversations", ["public_id"], unique=True)
    op.create_index(
        "ix_conversations_user_last_message",
        "conversations",
        ["user_id", sa.text("last_message_at DESC")],
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            postgresql.ENUM("user", "assistant", name="message_role", create_type=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "provider_used",
            postgresql.ENUM("gemini", "grok", name="ai_provider", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ux_conversation_messages_public_id", "conversation_messages", ["public_id"], unique=True
    )
    op.create_index(
        "ix_conversation_messages_conversation_created",
        "conversation_messages",
        ["conversation_id", "created_at"],
    )

    op.create_foreign_key(
        "fk_conversations_summarized_until_message",
        "conversations",
        "conversation_messages",
        ["summarized_until_message_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "transaction", "conversation_message", name="embedding_source_type", create_type=False
            ),
            nullable=False,
        ),
        # bigint não-FK: fonte polimórfica (id de transactions OU de conversation_messages).
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("source_type", "source_id", name="ux_embeddings_source"),
    )
    op.create_index("ix_embeddings_user_id", "embeddings", ["user_id"])
    op.execute(
        "CREATE INDEX embeddings_embedding_hnsw_idx "
        "ON embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS embeddings_embedding_hnsw_idx")
    op.drop_index("ix_embeddings_user_id", table_name="embeddings")
    op.drop_table("embeddings")

    op.drop_constraint(
        "fk_conversations_summarized_until_message", "conversations", type_="foreignkey"
    )

    op.drop_index(
        "ix_conversation_messages_conversation_created", table_name="conversation_messages"
    )
    op.drop_index("ux_conversation_messages_public_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    op.drop_index("ix_conversations_user_last_message", table_name="conversations")
    op.drop_index("ux_conversations_public_id", table_name="conversations")
    op.drop_table("conversations")

    embedding_source_type_enum.drop(op.get_bind(), checkfirst=True)
    ai_provider_enum.drop(op.get_bind(), checkfirst=True)
    message_role_enum.drop(op.get_bind(), checkfirst=True)
    conversation_channel_enum.drop(op.get_bind(), checkfirst=True)
