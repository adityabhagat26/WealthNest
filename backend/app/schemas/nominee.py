"""Schemas for nominee token access."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from backend.app.utils.datetime_utils import UTCDateTime


class NomineeCashBalanceRead(BaseModel):
    """Read-only cash balance row for nominee access."""

    currency: str = Field(..., description="Currency code (ISO 4217)")
    amount: str = Field(..., description="Cash balance amount as string")


class NomineeBankingBrokerRead(BaseModel):
    """Read-only banking summary per broker."""

    broker_id: int = Field(..., description="Broker ID")
    broker_name: str = Field(..., description="Broker name")
    cash_balances: list[NomineeCashBalanceRead] = Field(
        default_factory=list, description="Cash balances grouped by currency"
    )


class NomineeAssetHoldingRead(BaseModel):
    """Read-only asset holding row for nominee access."""

    broker_id: int = Field(..., description="Broker ID")
    broker_name: str = Field(..., description="Broker name")
    asset_id: int = Field(..., description="Asset ID")
    asset_name: str = Field(..., description="Asset display name")
    quantity: str = Field(..., description="Held quantity as string")
    asset_currency: str = Field(..., description="Asset currency code")


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
    banking_details: list[NomineeBankingBrokerRead] = Field(
        default_factory=list, description="Read-only per-broker banking balances"
    )
    account_cash_totals: list[NomineeCashBalanceRead] = Field(
        default_factory=list, description="Aggregated cash balances across all visible broker accounts"
    )
    asset_holdings: list[NomineeAssetHoldingRead] = Field(
        default_factory=list, description="Read-only per-broker asset holdings"
    )
