"""init

Revision ID: f84b66dfa65e
Revises:
Create Date: 2026-04-23 10:28:51.285350

"""

from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f84b66dfa65e"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    settings = context.get_context().opts['settings']

    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = '{settings.DB_APP_USER}') THEN
                EXECUTE 'CREATE USER "{settings.DB_APP_USER}" WITH PASSWORD ''{settings.DB_APP_PASS}''';
            END IF;
        END
        $$;
    """)

    op.execute(f'GRANT CONNECT ON DATABASE "{settings.DB_NAME}" TO "{settings.DB_APP_USER}";')
    op.execute(f'GRANT USAGE ON SCHEMA public TO "{settings.DB_APP_USER}";')

    op.execute(f"""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public 
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {settings.DB_APP_USER};
    """)

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", name="statusenum"
            ),
            nullable=False,
        ),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_amount", sa.Numeric(), nullable=False),
        sa.Column("saga_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)

    op.execute("ALTER TABLE orders ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE orders FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY orders_access_policy ON orders
        FOR ALL TO public
        USING (
            current_setting('app.current_user_role', true) = 'admin' 
            OR 
            user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
        WITH CHECK (
            current_setting('app.current_user_role', true) = 'admin' 
            OR 
            user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS orders_access_policy ON orders;")
    op.execute("ALTER TABLE orders DISABLE ROW LEVEL SECURITY;")
    op.drop_table("orders")
