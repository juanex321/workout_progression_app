"""Add recovery_days to feedback

Revision ID: 007_add_feedback_recovery_days
Revises: 006_add_set_drafts
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '007_add_feedback_recovery_days'
down_revision = '006_add_set_drafts'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("feedback")}
    if "recovery_days" not in columns:
        op.add_column("feedback", sa.Column("recovery_days", sa.Integer(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("feedback")}
    if "recovery_days" in columns:
        op.drop_column("feedback", "recovery_days")
