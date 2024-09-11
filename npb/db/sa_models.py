from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from npb.config import CommonConstants
from npb.db.core import mapper_registry

user_table = Table(
    "npb_user",
    mapper_registry.metadata,
    Column("seq_id", Integer, primary_key=True, nullable=False, unique=True, comment="Sequence id."),
    Column("telegram_id", String(100), primary_key=True, nullable=False, unique=True, comment="Telegram id."),
    Column("telegram_profile", String(200), comment="Telegram profile name."),
    Column("name", String(50), comment="User name."),
    Column(
        "services", JSONB,
        comment="User services ({service: {sub_service: true/false, ...}, ...})",
        server_default=text("'{}'::jsonb"),
    ),
    Column(
        "current_service",
        String(100),
        comment="Current picked service.",
        default=CommonConstants.TEMPORARY_DATA["current_service"],
    ),
    Column(
        "current_sub_service",
        String(100),
        comment="Current picked sub service.",
        default=CommonConstants.TEMPORARY_DATA["current_sub_service"],
    ),
    Column("phone_number", String(100), comment="Phone number."),
    Column("instagram_link", String(100), comment="Instagram link."),
    Column("description", String(500), comment="User description."),
    Column("is_master", Boolean, comment="Is user a master."),
    Column("is_admin", Boolean, comment="Is user an admin."),
    Column("state", String(100), comment="FSM storage state."),
    Column("edit_mode", String(100), comment="Edit mode."),
    Column("is_active", Boolean, comment="Is user subscription active.", default=True),
    Column("non_recogn_count", Integer, comment="Number of non recognized phrases.", default=0),
    Column("non_recogn_ts", DateTime, comment="Non recognized phrases last timestamp."),
    Column("fill_reg_form", Boolean, comment="Is registration form filled up.", default=False),
    Column("last_ts", DateTime, comment="Last activity timestamp."),
    Column("flood_count", Integer, comment="Number of user actions considered as flood."),
    Column("flood_ts", DateTime, comment="Flood last timestamp."),
    Column("ban_counter", Integer, comment="Ban counter."),
    Column("ban_ts", DateTime, comment="Ban last timestamp."),
    Column(
        "current_calendar",
        JSONB,
        comment="Current calendar state.",
        server_default=CommonConstants.TEMPORARY_DATA["current_calendar"],
    ),
    Column(
        "current_day",
        Integer,
        comment="Current picked day.",
        default=CommonConstants.TEMPORARY_DATA["current_day"],
    ),
    Column(
        "current_month",
        Integer,
        comment="Current picked month.",
        default=CommonConstants.TEMPORARY_DATA["current_month"],
    ),
    Column(
        "current_year",
        Integer,
        comment="Current picked year.",
        default=CommonConstants.TEMPORARY_DATA["current_year"],
    ),
    Column(
        "current_appointment",
        UUID,
        comment="Current picked appointment.",
        default=CommonConstants.TEMPORARY_DATA["current_appointment"],
    ),
    Column(
        "current_master",
        String(100),
        comment="Current picked master",
        default=CommonConstants.TEMPORARY_DATA["current_master"],
    ),
    Column(
        "current_page",
        Integer,
        comment="Current picked page",
        default=CommonConstants.TEMPORARY_DATA["current_page"],
    ),
)

appointment_table = Table(
    "appointment",
    # TODO: need an in here?
    mapper_registry.metadata,
    Column("auid", UUID, comment="Appointment unique id (as uuid).", default=uuid4),
    Column(
        "client_telegram_id",
        String(100),
        ForeignKey("npb_user.telegram_id"),
        comment="Client telegram id.",
        # unique=True,
    ),
    Column(
        "datetime",
        DateTime(timezone=True),
        comment="Appointment date and time.",
        nullable=False,
        unique=True,
    ),
    Column("service", String(100), comment="Chosen service."),
    Column(
        "master_telegram_id",
        String(100),
        ForeignKey("npb_user.telegram_id"),
        comment="Master telegram id.",
        # unique=True,
    ),
    Column("is_reserved", Boolean, comment="Is slot reserved.", default=False),
    Column(
        "notifications", Integer, comment="How many notifications was sent for this appointment.",
        server_default=text("0")
    ),
    Column(
        "notification_ts", DateTime(timezone=True), comment="Last notification ts"
    ),
    UniqueConstraint("master_telegram_id", "datetime"),
)
