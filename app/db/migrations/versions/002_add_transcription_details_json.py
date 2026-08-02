"""Add details_json column to transcriptions table.

Revision ID: 002_add_transcription_details_json
Revises: 001_initial
Create Date: 2026-08-02 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_add_transcription_details_json"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transcriptions",
        sa.Column("details_json", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transcriptions", "details_json")
