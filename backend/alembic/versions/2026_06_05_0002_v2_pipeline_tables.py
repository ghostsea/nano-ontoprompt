"""v2 pipeline tables

Revision ID: 0002_v2_pipeline
Revises:
Create Date: 2026-06-05

"""
from alembic import op
import sqlalchemy as sa

revision = '0002_v2_pipeline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. v2_connections
    op.create_table(
        'v2_connections',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('kind', sa.String(50), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='inactive'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 2. v2_datasets
    op.create_table(
        'v2_datasets',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('source_connection_id', sa.String(), sa.ForeignKey('v2_connections.id'), nullable=True),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('schema_json', sa.JSON(), nullable=True),
        sa.Column('latest_version_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 3. v2_dataset_versions
    op.create_table(
        'v2_dataset_versions',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('dataset_id', sa.String(), sa.ForeignKey('v2_datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('rowcount', sa.BigInteger(), nullable=True),
        sa.Column('storage_uri', sa.Text(), nullable=True),
        sa.Column('checksum', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 4. v2_media_items
    op.create_table(
        'v2_media_items',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('dataset_version_id', sa.String(), sa.ForeignKey('v2_dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('media_type', sa.String(20), nullable=False),
        sa.Column('storage_uri', sa.Text(), nullable=False),
        sa.Column('ocr_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('ocr_result_uri', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 5. v2_pipelines
    op.create_table(
        'v2_pipelines',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('source_dataset_id', sa.String(), sa.ForeignKey('v2_datasets.id'), nullable=True),
        sa.Column('route', sa.String(1), nullable=False),
        sa.Column('spec', sa.JSON(), nullable=False),
        sa.Column('target_curated_ids', sa.JSON(), nullable=True),
        sa.Column('schedule_cron', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_by', sa.String(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 6. v2_pipeline_runs
    op.create_table(
        'v2_pipeline_runs',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('pipeline_id', sa.String(), sa.ForeignKey('v2_pipelines.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stats', sa.JSON(), nullable=True),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('dataset_version_id', sa.String(), sa.ForeignKey('v2_dataset_versions.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 7. v2_curated_datasets
    op.create_table(
        'v2_curated_datasets',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('pipeline_id', sa.String(), sa.ForeignKey('v2_pipelines.id'), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('schema_json', sa.JSON(), nullable=True),
        sa.Column('latest_version_id', sa.String(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending_review'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 8. v2_curated_reviews
    op.create_table(
        'v2_curated_reviews',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('curated_dataset_id', sa.String(), sa.ForeignKey('v2_curated_datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reviewer_id', sa.String(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 9. v2_curated_row_edits
    op.create_table(
        'v2_curated_row_edits',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('review_id', sa.String(), sa.ForeignKey('v2_curated_reviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('row_pk', sa.String(200), nullable=False),
        sa.Column('field_name', sa.String(200), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 10. v2_ontology_mappings
    op.create_table(
        'v2_ontology_mappings',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('ontology_id', sa.String(), sa.ForeignKey('ontology_projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('curated_dataset_id', sa.String(), sa.ForeignKey('v2_curated_datasets.id'), nullable=True),
        sa.Column('entity_class', sa.String(200), nullable=False),
        sa.Column('field_mapping', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 11. v2_ontology_link_mappings
    op.create_table(
        'v2_ontology_link_mappings',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('ontology_id', sa.String(), sa.ForeignKey('ontology_projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('src_dataset_id', sa.String(), sa.ForeignKey('v2_curated_datasets.id'), nullable=True),
        sa.Column('tgt_dataset_id', sa.String(), sa.ForeignKey('v2_curated_datasets.id'), nullable=True),
        sa.Column('relation_type', sa.String(100), nullable=False),
        sa.Column('src_key', sa.String(100), nullable=False),
        sa.Column('tgt_key', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('v2_ontology_link_mappings')
    op.drop_table('v2_ontology_mappings')
    op.drop_table('v2_curated_row_edits')
    op.drop_table('v2_curated_reviews')
    op.drop_table('v2_curated_datasets')
    op.drop_table('v2_pipeline_runs')
    op.drop_table('v2_pipelines')
    op.drop_table('v2_media_items')
    op.drop_table('v2_dataset_versions')
    op.drop_table('v2_datasets')
    op.drop_table('v2_connections')
