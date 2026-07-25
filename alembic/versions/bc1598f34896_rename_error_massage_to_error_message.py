"""rename error_massage to error_message

Revision ID: bc1598f34896
Revises: b539e13ac795
Create Date: 2026-07-21 18:31:38.550767

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc1598f34896'
down_revision: Union[str, Sequence[str], None] = 'b539e13ac795'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "documents",
        "error_massage",
        new_column_name="error_message",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "documents",
        "error_message",
        new_column_name="error_message",
    )
