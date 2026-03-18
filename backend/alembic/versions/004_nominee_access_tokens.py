"""add nominee access tokens

Revision ID: 004_nominee_access_tokens
Revises: 003_nominee_threshold_unit
Create Date: 2026-03-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_nominee_access_tokens"
down_revision: Union[str, Sequence[str], None] = "003_nominee_threshold_unit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create nominee access token table."""
    op.create_table(
        "nominee_access_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("nominee_email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_nominee_access_tokens_nominee_email",
        "nominee_access_tokens",
        ["nominee_email"],
        unique=False,
    )
    op.create_index(
        "ix_nominee_access_tokens_token_hash",
        "nominee_access_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_nominee_access_tokens_user_id",
        "nominee_access_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_nominee_access_tokens_user_id_expires_at",
        "nominee_access_tokens",
        ["user_id", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop nominee access token table."""
    op.drop_index("ix_nominee_access_tokens_user_id_expires_at", table_name="nominee_access_tokens")
    op.drop_index("ix_nominee_access_tokens_user_id", table_name="nominee_access_tokens")
    op.drop_index("ix_nominee_access_tokens_token_hash", table_name="nominee_access_tokens")
    op.drop_index("ix_nominee_access_tokens_nominee_email", table_name="nominee_access_tokens")
    op.drop_table("nominee_access_tokens")
