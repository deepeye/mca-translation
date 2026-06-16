"""initial

Revision ID: ad7cfe796694
Revises:
Create Date: 2026-06-16 09:00:41.158320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ad7cfe796694'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('hashed_password', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    op.create_table(
        'translation_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=False),
        sa.Column('genre', sa.String(length=16), nullable=False),
        sa.Column('genre_confidence', sa.Float(), nullable=True),
        sa.Column('detected_terms', postgresql.JSONB(), nullable=True),
        sa.Column('strategy', sa.String(length=24), nullable=False),
        sa.Column('target_languages', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('glossary_ids', postgresql.ARRAY(sa.UUID(as_uuid=True)), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_translation_jobs_user_id'), 'translation_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_translation_jobs_status'), 'translation_jobs', ['status'], unique=False)

    op.create_table(
        'translation_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('language', sa.String(length=8), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('translated_text', sa.Text(), nullable=True),
        sa.Column('acceptance_score', sa.Integer(), nullable=False),
        sa.Column('audience_baseline', sa.String(length=32), nullable=True),
        sa.Column('risk_annotations', postgresql.JSONB(), nullable=True),
        sa.Column('quality_confidence', sa.Float(), nullable=True),
        sa.Column('decision_log_ids', postgresql.ARRAY(sa.UUID(as_uuid=True)), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['translation_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_translation_results_job_id'), 'translation_results', ['job_id'], unique=False)
    op.create_index(op.f('ix_translation_results_language'), 'translation_results', ['language'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_translation_results_language'), table_name='translation_results')
    op.drop_index(op.f('ix_translation_results_job_id'), table_name='translation_results')
    op.drop_table('translation_results')

    op.drop_index(op.f('ix_translation_jobs_status'), table_name='translation_jobs')
    op.drop_index(op.f('ix_translation_jobs_user_id'), table_name='translation_jobs')
    op.drop_table('translation_jobs')

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
