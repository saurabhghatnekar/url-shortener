"""Add RequestLog table for request logging

Revision ID: add_request_log_table
Revises: 87667dbe7833
Create Date: 2025-04-12 07:49:41

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_request_log_table'
down_revision = '87667dbe7833'
branch_labels = None
depends_on = None


def upgrade():
    # Create RequestLog table
    op.create_table('request_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=False),
        sa.Column('user_agent', sa.String(length=1024), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add index on timestamp for faster queries
    op.create_index(op.f('ix_request_logs_timestamp'), 'request_logs', ['timestamp'], unique=False)
    
    # Add index on path for faster filtering by endpoint
    op.create_index(op.f('ix_request_logs_path'), 'request_logs', ['path'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_request_logs_path'), table_name='request_logs')
    op.drop_index(op.f('ix_request_logs_timestamp'), table_name='request_logs')
    
    # Drop table
    op.drop_table('request_logs')
