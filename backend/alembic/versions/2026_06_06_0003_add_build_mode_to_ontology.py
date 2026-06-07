"""add build_mode to ontology_projects

Revision ID: 0003_add_build_mode
Revises: 0002_v2_pipeline
Create Date: 2026-06-06

"""
from alembic import op
import sqlalchemy as sa

revision = '0003_add_build_mode'
down_revision = '0002_v2_pipeline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ontology_projects',
        sa.Column('build_mode', sa.String(30), nullable=True, server_default='simple_llm')
    )


def downgrade() -> None:
    op.drop_column('ontology_projects', 'build_mode')
