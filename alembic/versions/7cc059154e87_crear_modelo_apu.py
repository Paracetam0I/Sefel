
"""crear modelo APU

Revision ID: 7cc059154e87
Revises: ab7c4e2173a2
Create Date: 2026-11-02 21:52:56.375104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '7cc059154e87'
down_revision: Union[str, Sequence[str], None] = 'ab7c4e2173a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'apu',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column('unit_cost', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column('updated_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.CheckConstraint('unit_cost >= 0', name='ck_apu_unit_cost_non_negative'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        'uq_apu_code_lower',
        'apu',
        [sa.text('lower(code)')],
        unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_apu_code_lower', table_name='apu')
    op.drop_table('apu')
