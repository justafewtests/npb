from datetime import datetime as python_datetime

from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from npb.config import CommonConstants
from npb.db.utils import create_timestamp_with_timezone


class UserModel(BaseModel):
    """
    User model.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    seq_id: int = Field(description="Sequence id.")
    telegram_id: str = Field(description="Telegram id.")
    telegram_profile: Optional[str] = Field(default=None, description="Telegram profile name.")
    name: Optional[str] = Field(default=None, description="User name.")
    services: Dict[str, Dict[str, bool]] = Field(default=None, description="User services.")
    current_service: Optional[str] = Field(
        default=CommonConstants.TEMPORARY_DATA["current_service"], description="Current picked service."
    )
    current_sub_service: Optional[str] = Field(
        default=CommonConstants.TEMPORARY_DATA["current_sub_service"], description="Current picked sub service."
    )
    phone_number: Optional[str] = Field(default=None, description="User phone number.")
    instagram_link: Optional[str] = Field(default=None, description="User instagram link.")
    description: Optional[str] = Field(default=None, description="User description.")
    is_master: bool = Field(default=False, description="Is user a master.")
    is_admin: bool = Field(default=False, description="Is user a admin.")
    state: Optional[str] = Field(default=None, description="FSM storage state.")
    edit_mode: Optional[str] = Field(default=None, description="Edit mode.")
    is_active: bool = Field(default=True, description="Is user subscription active.")
    last_ts: Optional[python_datetime] = Field(default=python_datetime.now(), description="Last activity timestamp.")
    flood_count: Optional[int] = Field(default=0, description="Number of user actions considered as flood.")
    flood_ts: Optional[python_datetime] = Field(default=None, description="Flood last timestamp.")
    non_recogn_count: Optional[bool] = Field(default=None, description="Number of non recognized phrases.")
    non_recogn_ts: Optional[python_datetime] = Field(default=None, description="Non recognized phrases last timestamp.")
    ban_counter: Optional[int] = Field(default=None, description="Ban counter.")
    ban_ts: [python_datetime] = Field(default=None, description="Ban last timestamp.")
    fill_reg_form: bool = Field(default=False, description="Is registration form filled up")
    current_calendar: Optional[dict] = Field(default={}, description="Current calendar state.")
    current_day: Optional[int] = Field(
        default=CommonConstants.TEMPORARY_DATA["current_day"], description="Current picked day.")
    current_month: Optional[int] = Field(
        default=CommonConstants.TEMPORARY_DATA["current_month"], description="Current picked month.")
    current_year: Optional[int] = Field(
        default=CommonConstants.TEMPORARY_DATA["current_year"], description="Current picked year.")
    current_appointment: Optional[str] = Field(
        default=CommonConstants.TEMPORARY_DATA["current_appointment"], description="Current picked appointment.")
    current_master: Optional[str] = Field(
        default=CommonConstants.TEMPORARY_DATA["current_master"], description="Current picked master")
    current_page: Optional[int] = Field(
        default=CommonConstants.TEMPORARY_DATA["current_page"], description="Current picked page"
    )


class AppointmentModel(BaseModel):
    """
    Appointment model.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    auid: Optional[UUID] = Field(default=None, description="Appointment unique id (as uuid).")
    client_telegram_id: Optional[str] = Field(default=None, description="Client telegram id.")
    datetime: python_datetime = Field(description="Appointment date and time.")
    service: Optional[str] = Field(default=None, description="Chosen service.")
    master_telegram_id: str = Field(description="Master telegram id.")
    is_reserved: Optional[bool] = Field(default=False, description="Is slot reserved.")
    notifications: Optional[int] = Field(
        default=None, description="How many notifications was sent for this appointment."
    )
    notification_ts: Optional[python_datetime] = Field(
        description="Last notification ts.", default_factory=create_timestamp_with_timezone
    )


class AppointmentList(BaseModel):
    appointment_list: List[AppointmentModel] = Field(default=None, description="Appointments list")
