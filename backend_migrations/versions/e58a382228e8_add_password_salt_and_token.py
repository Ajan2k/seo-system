"""Add password_salt and token

Revision ID: e58a382228e8
Revises: bf27663c65e5
Create Date: 2026-03-04 15:33:13.561214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e58a382228e8'
down_revision: Union[str, Sequence[str], None] = 'bf27663c65e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('password_salt', sa.String(length=200), nullable=False, server_default=''))
    op.add_column('users', sa.Column('token', sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'token')
    op.drop_column('users', 'password_salt')
