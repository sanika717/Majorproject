"""add_resolved_at_and_complaint_events

Revision ID: a1b2c3d4e5f6
Revises: 05fc282b8768
Create Date: 2026-10-31 19:18:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '05fc282b8768'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add resolved_at column to complaints
    op.add_column('complaints', sa.Column('resolved_at', sa.DateTime(), nullable=True))

    # 2. Backfill resolved_at with updated_at for rows already RESOLVED
    op.execute("UPDATE complaints SET resolved_at = updated_at WHERE status = 'RESOLVED' AND resolved_at IS NULL")

    # 3. Create complaint_events table
    op.create_table(
        'complaint_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('actor', sa.String(length=150), nullable=True),
        sa.Column('from_status', sa.String(length=50), nullable=False),
        sa.Column('to_status', sa.String(length=50), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_complaint_events_id'), 'complaint_events', ['id'], unique=False)
    op.create_index(op.f('ix_complaint_events_complaint_id'), 'complaint_events', ['complaint_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_complaint_events_complaint_id'), table_name='complaint_events')
    op.drop_index(op.f('ix_complaint_events_id'), table_name='complaint_events')
    op.drop_table('complaint_events')
    op.drop_column('complaints', 'resolved_at')
