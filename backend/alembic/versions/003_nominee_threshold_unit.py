"""add nominee threshold unit

Revision ID: 003_nominee_threshold_unit
Revises: 002_nominee_settings
Create Date: 2026-03-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_nominee_threshold_unit"
down_revision: Union[str, Sequence[str], None] = "002_nominee_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    """Return the existing column names for a SQLite table."""
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def upgrade() -> None:
    """Add nominee threshold unit to user_settings."""
    existing = _existing_columns("user_settings")

    if "nominee_threshold_unit" not in existing:
        op.add_column(
            "user_settings",
            sa.Column(
                "nominee_threshold_unit",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'days'"),
            ),
        )

    op.execute(
        "UPDATE user_settings SET nominee_threshold_unit = 'days' "
        "WHERE nominee_threshold_unit IS NULL OR nominee_threshold_unit = ''"
    )


def downgrade() -> None:
    """Remove nominee threshold unit from user_settings."""
    op.drop_column("user_settings", "nominee_threshold_unit")
