"""update_orders_model

Revision ID: 1c1b236731a4
Revises: f84b66dfa65e
Create Date: 2026-04-24 16:15:37.906428

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1c1b236731a4"
down_revision: Union[str, Sequence[str], None] = "f84b66dfa65e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("orders", sa.Column("idempotency_key", sa.Uuid(), nullable=False))
    op.create_unique_constraint(None, "orders", ["idempotency_key"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, "orders", type_="unique")
    op.drop_column("orders", "idempotency_key")
