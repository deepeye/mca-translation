"""add cultural context fields

Revision ID: 34e486ebe12c
Revises: ad7cfe796694
Create Date: 2026-06-16 23:36:17.844965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '34e486ebe12c'
down_revision: Union[str, Sequence[str], None] = 'ad7cfe796694'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'translation_jobs',
        sa.Column('cultural_sphere', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'translation_jobs',
        sa.Column('audience_type', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'translation_results',
        sa.Column('cultural_adaptation', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('translation_results', 'cultural_adaptation')
    op.drop_column('translation_jobs', 'audience_type')
    op.drop_column('translation_jobs', 'cultural_sphere')
