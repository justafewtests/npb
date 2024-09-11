"""Add notifications and notification_ts fields to Appointment table.

Revision ID: 03cffb433f70
Revises: c80c26fc0b12
Create Date: 2024-09-08 01:46:13.624182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03cffb433f70'
down_revision: Union[str, None] = 'c80c26fc0b12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointment",
        sa.Column(
            "notifications", sa.Integer, comment="How many notifications was sent for this appointment.",
            server_default=sa.text("0")
        ),
    )
    op.add_column(
        "appointment",
        sa.Column(
            "notification_ts", sa.DateTime(timezone=True), comment="Last notification ts"
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "appointment",
        "notifications"
    )
    op.drop_column(
        "appointment",
        "notification_ts"
    )
