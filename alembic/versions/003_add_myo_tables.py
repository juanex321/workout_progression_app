"""Add myo reps tables

Revision ID: 003_add_myo_tables
Revises: 002_add_unique_set_constraint
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '003_add_myo_tables'
down_revision = '002_add_unique_set_constraint'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = set(inspector.get_table_names())

    if 'myo_sessions' not in existing:
        op.create_table(
            'myo_sessions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('completed', sa.Integer(), nullable=False, server_default='0'),
        )

    if 'myo_exercise_sessions' not in existing:
        op.create_table(
            'myo_exercise_sessions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('myo_session_id', sa.Integer(), sa.ForeignKey('myo_sessions.id'), nullable=False),
            sa.Column('exercise_id', sa.Integer(), sa.ForeignKey('exercises.id'), nullable=False),
            sa.Column('target_mini_sets', sa.Integer(), nullable=True),
            sa.Column('completed_mini_sets', sa.Integer(), nullable=True),
            sa.Column('workload_feedback', sa.Integer(), nullable=True),
            sa.Column('completed', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if 'myo_activation_sets' not in existing:
        op.create_table(
            'myo_activation_sets',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('exercise_session_id', sa.Integer(), sa.ForeignKey('myo_exercise_sessions.id'), nullable=False, unique=True),
            sa.Column('weight', sa.Float(), nullable=True),
            sa.Column('reps', sa.Integer(), nullable=True),
            sa.Column('logged_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if 'myo_mini_sets' not in existing:
        op.create_table(
            'myo_mini_sets',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('exercise_session_id', sa.Integer(), sa.ForeignKey('myo_exercise_sessions.id'), nullable=False),
            sa.Column('order_index', sa.Integer(), nullable=False),
            sa.Column('reps', sa.Integer(), nullable=False),
            sa.Column('logged_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if 'myo_exercise_calibration' not in existing:
        op.create_table(
            'myo_exercise_calibration',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('exercise_id', sa.Integer(), sa.ForeignKey('exercises.id'), nullable=False, unique=True),
            sa.Column('calibrated', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('baseline_mini_sets', sa.Integer(), nullable=True),
            sa.Column('current_target', sa.Integer(), nullable=True),
            sa.Column('calibration_sessions_done', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('calibration_mini_sets_sum', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('consecutive_hard_sessions', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade():
    op.drop_table('myo_exercise_calibration')
    op.drop_table('myo_mini_sets')
    op.drop_table('myo_activation_sets')
    op.drop_table('myo_exercise_sessions')
    op.drop_table('myo_sessions')
