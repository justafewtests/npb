"""create user table

Revision ID: c80c26fc0b12
Revises: 
Create Date: 2024-01-17 21:01:04.571067

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from nbp.config import CommonConstants

# revision identifiers, used by Alembic.
revision: str = 'c80c26fc0b12'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "npb_user",
        sa.Column("seq_id", sa.Integer, primary_key=True, nullable=False, unique=True, comment="Sequence id."),
        sa.Column("telegram_id", sa.String(100), primary_key=True, nullable=False, unique=True, comment="Telegram id."),
        sa.Column("telegram_profile", sa.String(200), comment="Telegram profile name."),
        sa.Column("name", sa.String(50), comment="User name."),
        sa.Column(
            "services", JSONB,
            comment="User services ({service: {sub_service: true/false, ...}, ...})",
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "current_service",
            sa.String(100),
            comment="Current picked service.",
            default=CommonConstants.TEMPORARY_DATA["current_service"],
        ),
        sa.Column(
            "current_sub_service",
            sa.String(100),
            comment="Current picked sub service.",
            default=CommonConstants.TEMPORARY_DATA["current_sub_service"],
        ),
        sa.Column("phone_number", sa.String(100), comment="Phone number."),
        sa.Column("instagram_link", sa.String(100), comment="Instagram link."),
        sa.Column("description", sa.String(500), comment="User description."),
        sa.Column("is_master", sa.Boolean, comment="Is user a master."),
        sa.Column("is_admin", sa.Boolean, comment="Is user an admin."),
        sa.Column("state", sa.String(100), comment="FSM storage state."),
        sa.Column("edit_mode", sa.String(100), comment="Edit mode."),
        sa.Column("is_active", sa.Boolean, comment="Is user subscription active.", default=True),
        sa.Column("non_recogn_count", sa.Integer, comment="Number of non recognized phrases.", default=0),
        sa.Column("non_recogn_ts", sa.DateTime, comment="Non recognized phrases last timestamp."),
        sa.Column("fill_reg_form", sa.Boolean, comment="Is registration form filled up.", default=False),
        sa.Column("last_ts", sa.DateTime, comment="Last activity timestamp."),
        sa.Column("flood_count", sa.Integer, comment="Number of user actions considered as flood."),
        sa.Column("flood_ts", sa.DateTime, comment="Flood last timestamp."),
        sa.Column("ban_counter", sa.Integer, comment="Ban counter."),
        sa.Column("ban_ts", sa.DateTime, comment="Ban last timestamp."),
        sa.Column(
            "current_calendar",
            JSONB,
            comment="Current calendar state.",
            server_default=CommonConstants.TEMPORARY_DATA["current_calendar"],
        ),
        sa.Column(
            "current_day",
            sa.Integer,
            comment="Current picked day.",
            default=CommonConstants.TEMPORARY_DATA["current_day"],
        ),
        sa.Column(
            "current_month",
            sa.Integer,
            comment="Current picked month.",
            default=CommonConstants.TEMPORARY_DATA["current_month"],
        ),
        sa.Column(
            "current_year",
            sa.Integer,
            comment="Current picked year.",
            default=CommonConstants.TEMPORARY_DATA["current_year"],
        ),
        sa.Column(
            "current_appointment",
            sa.UUID,
            comment="Current picked appointment.",
            default=CommonConstants.TEMPORARY_DATA["current_appointment"],
        ),
        sa.Column(
            "current_master",
            sa.String(100),
            comment="Current picked master",
            default=CommonConstants.TEMPORARY_DATA["current_master"],
        ),
        sa.Column(
            "current_page",
            sa.Integer,
            comment="Current picked page",
            default=CommonConstants.TEMPORARY_DATA["current_page"],
        ),
    )
    op.create_table(
        'appointment',
        sa.Column("auid", sa.UUID, comment="Appointment unique id (as uuid).", default=uuid4),
        sa.Column(
            "client_telegram_id",
            sa.String(100),
            sa.ForeignKey("npb_user.telegram_id"),
            comment="Client telegram id.",
            # unique=True,
        ),
        sa.Column(
            "datetime",
            sa.DateTime(timezone=True),
            comment="Appointment date and time.",
            nullable=False,
            unique=True,
        ),
        sa.Column("service", sa.String(100), comment="Chosen service."),
        sa.Column(
            "master_telegram_id",
            sa.String(100),
            sa.ForeignKey("npb_user.telegram_id"),
            comment="Master telegram id.",
            # unique=True,
        ),
        sa.Column("is_reserved", sa.Boolean, comment="Is slot reserved.", default=False),
        sa.UniqueConstraint("master_telegram_id", "datetime"),
    )


def downgrade() -> None:
    op.drop_table('npb_user')
    op.drop_table('appointment')
