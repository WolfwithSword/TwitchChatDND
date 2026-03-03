"""Add pocket to sources constraint

Revision ID: add_pocket
Revises: 85bfff5ba6a6
Create Date: 2026-03-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_pocket"
down_revision: Union[str, None] = "85bfff5ba6a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename old table
    op.rename_table("voices", "voices_old")

    # Create new table with updated constraint including 'pocket'
    op.create_table(
        "voices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.CheckConstraint(
            "source IN ('local', 'elevenlabs', 'streamelements', 'pocket')",
            name="chk_source_valid_val",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("uid"),
    )

    # Copy data from old table
    op.execute(
        """
        INSERT INTO voices (id, name, uid, source)
        SELECT id, name, uid, source FROM voices_old
    """
    )

    # Drop old table
    op.drop_table("voices_old")


def downgrade() -> None:
    # Remove pocket voices before downgrading
    op.execute("DELETE FROM voices WHERE source = 'pocket'")

    # Rename old table
    op.rename_table("voices", "voices_old")

    # Create table with old constraint (without 'pocket')
    op.create_table(
        "voices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.CheckConstraint(
            "source IN ('local', 'elevenlabs', 'streamelements')",
            name="chk_source_valid_val",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("uid"),
    )

    # Copy data from old table
    op.execute(
        """
        INSERT INTO voices (id, name, uid, source)
        SELECT id, name, uid, source FROM voices_old
    """
    )

    # Drop old table
    op.drop_table("voices_old")
