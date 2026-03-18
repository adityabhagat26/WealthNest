"""add nominee settings fields

Revision ID: 002_nominee_settings
Revises: 001_initial
Create Date: 2026-03-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_nominee_settings"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    """Return the existing column names for a SQLite table."""
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def upgrade() -> None:
    """Add nominee-related columns to user_settings."""
    existing = _existing_columns("user_settings")

    if "nominee_email" not in existing:
        op.add_column("user_settings", sa.Column("nominee_email", sa.String(length=255), nullable=True))
    if "nominee_enabled" not in existing:
        op.add_column(
            "user_settings",
            sa.Column("nominee_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    if "nominee_threshold_days" not in existing:
        op.add_column(
            "user_settings",
            sa.Column(
                "nominee_threshold_days",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("30"),
            ),
        )
    if "last_activity_at" not in existing:
        op.add_column(
            "user_settings",
            sa.Column(
                "last_activity_at",
                sa.DateTime(),
                nullable=True,
            ),
        )
    if "nominee_last_notified_at" not in existing:
        op.add_column(
            "user_settings",
            sa.Column("nominee_last_notified_at", sa.DateTime(), nullable=True),
        )

    op.execute("UPDATE user_settings SET nominee_enabled = 0 WHERE nominee_enabled IS NULL")
    op.execute("UPDATE user_settings SET nominee_threshold_days = 30 WHERE nominee_threshold_days IS NULL")
    op.execute("UPDATE user_settings SET last_activity_at = CURRENT_TIMESTAMP WHERE last_activity_at IS NULL")


def downgrade() -> None:
    """Remove nominee-related columns from user_settings."""
    op.drop_column("user_settings", "nominee_last_notified_at")
    op.drop_column("user_settings", "last_activity_at")
    op.drop_column("user_settings", "nominee_threshold_days")
    op.drop_column("user_settings", "nominee_enabled")
    op.drop_column("user_settings", "nominee_email")
