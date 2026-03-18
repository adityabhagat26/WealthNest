"""Schemas for nominee token access."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from backend.app.utils.datetime_utils import UTCDateTime


class NomineeAccessRead(BaseModel):
    """Read-only nominee access payload."""

    account_holder_username: str = Field(..., description="Username of the account holder")
    nominee_email: EmailStr = Field(..., description="Nominee email tied to the token")
    access_scope: Literal["read_only"] = Field("read_only", description="Granted nominee access scope")
    expires_at: UTCDateTime = Field(..., description="Token expiration timestamp")
    last_activity_at: UTCDateTime | None = Field(None, description="Last authenticated activity")
    nominee_threshold_days: int = Field(..., ge=1, description="Configured inactivity threshold value")
    nominee_threshold_unit: Literal["days", "hours", "minutes", "seconds"] = Field(
        ..., description="Configured inactivity threshold unit"
    )
    broker_count: int = Field(..., ge=0, description="Number of brokers visible in nominee summary")
    broker_names: list[str] = Field(default_factory=list, description="Broker names visible in nominee summary")
