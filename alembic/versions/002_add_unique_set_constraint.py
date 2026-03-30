"""Add unique constraint on (session_id, workout_exercise_id, set_number) in sets table

Revision ID: 002_add_unique_set_constraint
Revises: 001_add_session_fields
Create Date: 2026-03-30
"""
from alembic import op
from sqlalchemy import inspect

revision = '002_add_unique_set_constraint'
down_revision = '001_add_session_fields'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'sets' not in inspector.get_table_names():
        print("sets table doesn't exist yet — constraint will be created by init_db()")
        return

    existing_constraints = [c['name'] for c in inspector.get_unique_constraints('sets')]
    if 'uq_set_session_exercise_number' in existing_constraints:
        print("uq_set_session_exercise_number already exists")
        return

    op.create_unique_constraint(
        'uq_set_session_exercise_number',
        'sets',
        ['session_id', 'workout_exercise_id', 'set_number'],
    )
    print("Added uq_set_session_exercise_number constraint")


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'sets' not in inspector.get_table_names():
        return

    existing_constraints = [c['name'] for c in inspector.get_unique_constraints('sets')]
    if 'uq_set_session_exercise_number' in existing_constraints:
        op.drop_constraint('uq_set_session_exercise_number', 'sets', type_='unique')
        print("Removed uq_set_session_exercise_number constraint")
