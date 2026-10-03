"""extend feedback table

Revision ID: a1b2c3d4e5f6
Revises: fcd68f69f49f
Create Date: 2026-08-16 10:00:00.000000

"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = 'fcd68f69f49f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

feedback_type_enum = postgresql.ENUM("praise", "suggestion", "bug", "other", name="feedback_type")


def upgrade() -> None:
    """Upgrade schema.

    Build-context-08 §2.2/2.3: estende a base mínima do feedback
    (build-context-06) com type/nps_score/subject, corrige `message` para
    texto plano (RN-05 nunca listou `message`/`subject` de Feedback entre
    os campos AES — a criptografia da base mínima estava fora da regra) e
    troca a identidade de BigInteger+public_id/ULID para UUID puro, já
    que este agregado nunca tem endpoint `show`/update/delete individual.
    """
    bind = op.get_bind()
    feedback_type_enum.create(bind, checkfirst=True)

    op.add_column(
        "feedback",
        sa.Column(
            "type", postgresql.ENUM("praise", "suggestion", "bug", "other", name="feedback_type", create_type=False),
            nullable=False,
            server_default="other",
        ),
    )
    op.add_column("feedback", sa.Column("nps_score", sa.SmallInteger(), nullable=True))
    op.add_column("feedback", sa.Column("subject", sa.String(length=150), nullable=True))
    op.create_check_constraint(
        "ck_feedback_nps_score_range",
        "feedback",
        "nps_score IS NULL OR nps_score BETWEEN 0 AND 10",
    )

    _decrypt_existing_messages(bind)
    op.alter_column("feedback", "message", type_=sa.Text(), existing_nullable=False)

    op.drop_index("ux_feedback_public_id", table_name="feedback")
    op.drop_column("feedback", "public_id")

    op.add_column("feedback", sa.Column("new_id", postgresql.UUID(as_uuid=True), nullable=True))
    feedback_table = sa.table(
        "feedback", sa.column("id", sa.BigInteger()), sa.column("new_id", postgresql.UUID())
    )
    result = bind.execute(sa.select(feedback_table.c.id))
    for row in result:
        bind.execute(
            feedback_table.update()
            .where(feedback_table.c.id == row.id)
            .values(new_id=uuid.uuid4())
        )
    op.alter_column("feedback", "new_id", nullable=False)
    op.drop_constraint("feedback_pkey", "feedback", type_="primary")
    op.drop_column("feedback", "id")
    op.alter_column("feedback", "new_id", new_column_name="id")
    op.create_primary_key("feedback_pkey", "feedback", ["id"])


def _decrypt_existing_messages(bind: sa.engine.Connection) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Passo de dados — decripta (Fernet/AES) as mensagens
    gravadas pela base mínima do build-context-06/07 antes de o `message`
    passar a ser tratado como texto plano pelo model (RN-05 corrigida).
    Sem isso, o ciphertext antigo viraria lixo ilegível permanentemente.
    """
    from cryptography.fernet import InvalidToken

    from src.infrastructure.security.encrypted_string import EncryptionService

    encryption_service = EncryptionService()
    feedback_table = sa.table(
        "feedback", sa.column("id", sa.BigInteger()), sa.column("message", sa.String())
    )
    rows = bind.execute(sa.select(feedback_table.c.id, feedback_table.c.message)).fetchall()
    for row in rows:
        try:
            plain_message = encryption_service.decrypt(row.message)
        except InvalidToken:
            # Mensagem já em texto plano (ex.: linha inserida manualmente em teste) — mantém como está.
            continue
        bind.execute(
            feedback_table.update()
            .where(feedback_table.c.id == row.id)
            .values(message=plain_message)
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    op.add_column("feedback", sa.Column("old_id", sa.BigInteger(), nullable=True))
    feedback_table = sa.table(
        "feedback", sa.column("id", postgresql.UUID()), sa.column("old_id", sa.BigInteger())
    )
    rows = bind.execute(sa.select(feedback_table.c.id)).fetchall()
    for sequence_value, row in enumerate(rows, start=1):
        bind.execute(
            feedback_table.update()
            .where(feedback_table.c.id == row.id)
            .values(old_id=sequence_value)
        )
    op.alter_column("feedback", "old_id", nullable=False)
    op.drop_constraint("feedback_pkey", "feedback", type_="primary")
    op.drop_column("feedback", "id")
    op.alter_column("feedback", "old_id", new_column_name="id")
    op.create_primary_key("feedback_pkey", "feedback", ["id"])
    op.execute(
        "ALTER TABLE feedback ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY "
        f"(START WITH {len(rows) + 1})"
    )

    op.add_column("feedback", sa.Column("public_id", sa.String(length=26), nullable=True))
    op.create_index("ux_feedback_public_id", "feedback", ["public_id"], unique=True)

    op.drop_constraint("ck_feedback_nps_score_range", "feedback", type_="check")
    op.drop_column("feedback", "subject")
    op.drop_column("feedback", "nps_score")
    op.drop_column("feedback", "type")
    feedback_type_enum.drop(op.get_bind(), checkfirst=True)
