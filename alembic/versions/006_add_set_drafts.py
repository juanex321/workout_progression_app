"""Add set_drafts table for server-side autosave of unlogged sets

Revision ID: 006_add_set_drafts
Revises: 005_remove_rir_column
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '006_add_set_drafts'
down_revision = '005_remove_rir_column'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'set_drafts' in inspector.get_table_names():
        print("set_drafts already exists")
        return

    op.create_table(
        'set_drafts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('sessions.id'), nullable=False),
        sa.Column('workout_exercise_id', sa.Integer(), sa.ForeignKey('workout_exercises.id'), nullable=False),
        sa.Column('payload', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('session_id', 'workout_exercise_id', name='uq_set_draft_session_exercise'),
    )
    print("Added set_drafts table")


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'set_drafts' in inspector.get_table_names():
        op.drop_table('set_drafts')
        print("Removed set_drafts table")
