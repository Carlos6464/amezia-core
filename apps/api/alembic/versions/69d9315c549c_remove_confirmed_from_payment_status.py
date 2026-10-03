"""remove confirmed from payment status

Revision ID: 69d9315c549c
Revises: 96ecdf3b1016
Create Date: 2026-08-09 15:47:17.868144

"""
from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '69d9315c549c'
down_revision: str | Sequence[str] | None = '96ecdf3b1016'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Feedback do usuário (2026-08-09, mesmo dia): "confirmado" não
    acrescenta nada sobre "pago" — só dois status fazem sentido. Postgres
    não suporta remover valor de enum diretamente, então o padrão seguro
    é: renomear o enum antigo, criar o novo sem o valor, migrar a coluna
    com um `CASE` (linhas 'confirmed' viram 'paid'), trocar o default,
    derrubar o enum antigo.
    """
    op.execute("ALTER TYPE payment_status RENAME TO payment_status_old")
    new_enum = postgresql.ENUM("pending", "paid", name="payment_status")
    new_enum.create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE transactions "
        "ALTER COLUMN status DROP DEFAULT, "
        "ALTER COLUMN status TYPE payment_status USING ("
        "  CASE status::text WHEN 'confirmed' THEN 'paid' ELSE status::text END"
        ")::payment_status, "
        "ALTER COLUMN status SET DEFAULT 'paid'::payment_status"
    )
    op.execute("DROP TYPE payment_status_old")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TYPE payment_status RENAME TO payment_status_new")
    old_enum = postgresql.ENUM("pending", "paid", "confirmed", name="payment_status")
    old_enum.create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE transactions "
        "ALTER COLUMN status DROP DEFAULT, "
        "ALTER COLUMN status TYPE payment_status USING status::text::payment_status, "
        "ALTER COLUMN status SET DEFAULT 'confirmed'::payment_status"
    )
    op.execute("DROP TYPE payment_status_new")
