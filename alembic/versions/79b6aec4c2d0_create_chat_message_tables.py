"""create_chat_message_tables

Revision ID: 79b6aec4c2d0
Revises:
Create Date: 2026-05-11 23:31:18.119807

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '79b6aec4c2d0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create chats and messages tables."""
    # Create chats table
    op.create_table(
        'chats',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_chats'))
    )
    op.create_index(op.f('ix_chats_created_at'), 'chats', ['created_at'], unique=False)
    op.create_index(op.f('ix_title'), 'chats', ['title'], unique=False)

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('chat_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name=op.f('ck_messages_valid_role')),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], name=op.f('fk_messages_chat_id_chats'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_messages'))
    )
    op.create_index(op.f('ix_chat_id'), 'messages', ['chat_id'], unique=False)
    op.create_index(op.f('ix_messages_chat_id_created_at'), 'messages', ['chat_id', 'created_at'], unique=False)


def downgrade() -> None:
    """Drop messages and chats tables."""
    op.drop_index(op.f('ix_messages_chat_id_created_at'), table_name='messages')
    op.drop_index(op.f('ix_chat_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_title'), table_name='chats')
    op.drop_index(op.f('ix_chats_created_at'), table_name='chats')
    op.drop_table('chats')
