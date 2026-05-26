"""create_task_table

Revision ID: 002_create_task_table
Revises: 79b6aec4c2d0
Create Date: 2026-05-11 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '002_create_task_table'
down_revision = '79b6aec4c2d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tasks table."""
    op.create_table(
        'tasks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('task_type', sa.String(length=100), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('chat_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name=op.f('ck_tasks_valid_status')
        ),
        sa.ForeignKeyConstraint(
            ['chat_id'],
            ['chats.id'],
            name=op.f('fk_tasks_chat_id_chats'),
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tasks'))
    )
    op.create_index(op.f('ix_task_type'), 'tasks', ['task_type'], unique=False)
    op.create_index(op.f('ix_user_id'), 'tasks', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_id'), 'tasks', ['chat_id'], unique=False)
    op.create_index(op.f('ix_status'), 'tasks', ['status'], unique=False)
    op.create_index(op.f('ix_tasks_created_at'), 'tasks', ['created_at'], unique=False)


def downgrade() -> None:
    """Drop tasks table."""
    op.drop_index(op.f('ix_tasks_created_at'), table_name='tasks')
    op.drop_index(op.f('ix_status'), table_name='tasks')
    op.drop_index(op.f('ix_chat_id'), table_name='tasks')
    op.drop_index(op.f('ix_user_id'), table_name='tasks')
    op.drop_index(op.f('ix_task_type'), table_name='tasks')
    op.drop_table('tasks')
