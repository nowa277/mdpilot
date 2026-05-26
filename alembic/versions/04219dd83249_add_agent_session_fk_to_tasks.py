"""add agent_session_fk to tasks

Revision ID: 04219dd83249
Revises: 004
Create Date: 2026-05-13 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '04219dd83249'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
