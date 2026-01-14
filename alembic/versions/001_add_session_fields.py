"""Add session_number, rotation_index, and completed fields to sessions table

Revision ID: 001_add_session_fields
Revises: 
Create Date: 2026-01-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '001_add_session_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add new columns to sessions table if they don't exist."""
    # Get connection to check existing columns
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if sessions table exists
    if 'sessions' not in inspector.get_table_names():
        print("⚠️  Sessions table doesn't exist yet - will be created by init_db()")
        return
    
    existing_columns = [col['name'] for col in inspector.get_columns('sessions')]
    
    # Add session_number if it doesn't exist
    if 'session_number' not in existing_columns:
        op.add_column('sessions', sa.Column('session_number', sa.Integer(), nullable=False, server_default='1'))
        print("✅ Added session_number column")
    else:
        print("ℹ️  session_number column already exists")
    
    # Add rotation_index if it doesn't exist
    if 'rotation_index' not in existing_columns:
        op.add_column('sessions', sa.Column('rotation_index', sa.Integer(), nullable=False, server_default='0'))
        print("✅ Added rotation_index column")
    else:
        print("ℹ️  rotation_index column already exists")
    
    # Add completed if it doesn't exist
    if 'completed' not in existing_columns:
        op.add_column('sessions', sa.Column('completed', sa.Integer(), nullable=False, server_default='0'))
        print("✅ Added completed column")
    else:
        print("ℹ️  completed column already exists")


def downgrade():
    """Remove the new columns (for rollback)."""
    # Get connection to check existing columns
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if 'sessions' not in inspector.get_table_names():
        print("⚠️  Sessions table doesn't exist")
        return
    
    existing_columns = [col['name'] for col in inspector.get_columns('sessions')]
    
    if 'completed' in existing_columns:
        op.drop_column('sessions', 'completed')
        print("⚠️  Removed completed column")
    
    if 'rotation_index' in existing_columns:
        op.drop_column('sessions', 'rotation_index')
        print("⚠️  Removed rotation_index column")
    
    if 'session_number' in existing_columns:
        op.drop_column('sessions', 'session_number')
        print("⚠️  Removed session_number column")
