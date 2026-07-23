"""Remove rir column from sets

Revision ID: 005_remove_rir_column
Revises: 004_remove_myo_tables
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '005_remove_rir_column'
down_revision = '004_remove_myo_tables'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("sets")}
    if "rir" in columns:
        op.drop_column("sets", "rir")


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("sets")}
    if "rir" not in columns:
        op.add_column("sets", sa.Column("rir", sa.Integer(), nullable=True))
