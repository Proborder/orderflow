"""init saga_state

Revision ID: fb00d6570891
Revises:
Create Date: 2026-04-27 22:16:35.962416

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fb00d6570891"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "saga_state",
        sa.Column("saga_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "CREATED",
                "INVENTORY_RESERVING",
                "INVENTORY_RESERVED",
                "PAYMENT_CHARGING",
                "COMPLETED",
                "COMPENSATING_INVENTORY",
                "CANCELLED",
                "FAILED",
                name="stateenum",
            ),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("saga_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("saga_state")
