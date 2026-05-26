"""extend tasks table for background execution

Revision ID: 004
Revises: 003
Create Date: 2026-05-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns first
    op.add_column('tasks', sa.Column('agent_session_id', sa.String(length=36), nullable=True))
    op.add_column('tasks', sa.Column('progress_percentage', sa.Float(), nullable=True))
    op.add_column('tasks', sa.Column('current_stage', sa.String(length=255), nullable=True))
    
    # Then add constraints and indexes in batch mode
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_tasks_agent_session_id',
            'agent_sessions',
            ['agent_session_id'], ['id'],
            ondelete='SET NULL'
        )
        batch_op.create_index('ix_tasks_agent_session_id', ['agent_session_id'])


def downgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index('ix_tasks_agent_session_id')
        batch_op.drop_constraint('fk_tasks_agent_session_id', type_='foreignkey')
    
    op.drop_column('tasks', 'current_stage')
    op.drop_column('tasks', 'progress_percentage')
    op.drop_column('tasks', 'agent_session_id')
