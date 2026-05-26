"""add agent sessions table

Revision ID: 003
Revises: 002
Create Date: 2026-05-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003'
down_revision = '002_create_task_table'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('context_messages', sa.JSON(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('iteration_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_iterations', sa.Integer(), nullable=False),
    )
    op.create_index('ix_agent_sessions_id', 'agent_sessions', ['id'])


def downgrade():
    op.drop_index('ix_agent_sessions_id', 'agent_sessions')
    op.drop_table('agent_sessions')
