"""add retry_after in saga_state

Revision ID: 47a0aefd085c
Revises: 048f4e3f03ee
Create Date: 2026-05-01 19:50:20.656632

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "47a0aefd085c"
down_revision: Union[str, Sequence[str], None] = "048f4e3f03ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("saga_state", sa.Column("retry_after", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("saga_state", "retry_after")
