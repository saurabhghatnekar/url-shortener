"""Create users and urls tables

Revision ID: 371264788012
Revises: 
Create Date: 2025-02-26 16:58:49.476378

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '371264788012'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('api_key', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('api_key'),
        sa.UniqueConstraint('email')
    )
    
    # Create urls table
    op.create_table('urls',
        sa.Column('short_code', sa.String(length=6), nullable=False),
        sa.Column('original_url', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('click_count', sa.Integer(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('short_code')
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('urls')
    op.drop_table('users')
