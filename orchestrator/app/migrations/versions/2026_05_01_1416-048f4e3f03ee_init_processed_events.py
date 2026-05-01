"""Init processed events

Revision ID: 048f4e3f03ee
Revises: 7beb91a7b883
Create Date: 2026-05-01 14:16:42.934337

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "048f4e3f03ee"
down_revision: Union[str, Sequence[str], None] = "7beb91a7b883"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("saga_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["saga_id"],
            ["saga_state.saga_id"],
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("processed_events")
