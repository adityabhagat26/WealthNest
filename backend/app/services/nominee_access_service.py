"""
Nominee access token service.

Creates and validates expiring read-only access links for nominees.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.models import (
    Asset,
    Broker,
    BrokerUserAccess,
    NomineeAccessToken,
    Transaction,
    User,
    UserSettings,
)
from backend.app.utils.datetime_utils import ensure_utc, utcnow


def hash_nominee_token(raw_token: str) -> str:
    """Hash a raw nominee token for safe database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def build_nominee_access_url(raw_token: str) -> str:
    """Build the frontend nominee access URL from configuration."""
    base_url = get_settings().FRONTEND_BASE_URL.rstrip("/")
    return f"{base_url}/nominee-access?token={quote(raw_token)}"


async def create_nominee_access_link(
    session: AsyncSession,
    user: User,
    nominee_email: str,
) -> str:
    """Create a fresh nominee token and return its frontend access URL."""
    settings = get_settings()
    now = utcnow()

    # Revoke older active tokens for this nominee/user pair so the newest email wins.
    result = await session.execute(
        select(NomineeAccessToken).where(
            NomineeAccessToken.user_id == user.id,
            NomineeAccessToken.nominee_email == nominee_email,
            NomineeAccessToken.revoked_at.is_(None),
            NomineeAccessToken.expires_at > now,
        )
    )
    for existing_token in result.scalars().all():
        existing_token.revoked_at = now
        existing_token.updated_at = now
        session.add(existing_token)

    raw_token = secrets.token_urlsafe(32)
    ttl_hours = max(int(settings.NOMINEE_ACCESS_TOKEN_TTL_HOURS or 72), 1)
    token = NomineeAccessToken(
        user_id=user.id,
        nominee_email=nominee_email,
        token_hash=hash_nominee_token(raw_token),
        expires_at=now + timedelta(hours=ttl_hours),
        created_at=now,
        updated_at=now,
    )
    session.add(token)
    await session.commit()

    return build_nominee_access_url(raw_token)


async def get_nominee_access_token(
    session: AsyncSession,
    raw_token: str,
) -> NomineeAccessToken | None:
    """Return a valid nominee access token row, or None if invalid/expired/revoked."""
    now = utcnow()
    result = await session.execute(
        select(NomineeAccessToken).where(
            NomineeAccessToken.token_hash == hash_nominee_token(raw_token),
            NomineeAccessToken.revoked_at.is_(None),
        )
    )
    token = result.scalar_one_or_none()
    expires_at = ensure_utc(token.expires_at) if token is not None else None
    if token is None or expires_at is None or expires_at <= now:
        return None
    return token


async def touch_nominee_access_token(session: AsyncSession, token: NomineeAccessToken) -> None:
    """Update the last-used timestamp for a nominee token."""
    token.last_used_at = utcnow()
    token.updated_at = utcnow()
    session.add(token)
    await session.commit()


async def build_nominee_access_context(
    session: AsyncSession,
    token: NomineeAccessToken,
) -> dict:
    """Build the read-only nominee access payload."""
    user_result = await session.execute(select(User).where(User.id == token.user_id))
    user = user_result.scalar_one()

    settings_result = await session.execute(select(UserSettings).where(UserSettings.user_id == token.user_id))
    user_settings = settings_result.scalar_one_or_none()

    broker_names_result = await session.execute(
        select(Broker.name)
        .join(BrokerUserAccess, BrokerUserAccess.broker_id == Broker.id)
        .where(BrokerUserAccess.user_id == token.user_id)
        .order_by(Broker.name.asc())
    )
    broker_names = list(broker_names_result.scalars().all())

    broker_count_result = await session.execute(
        select(func.count())
        .select_from(BrokerUserAccess)
        .where(BrokerUserAccess.user_id == token.user_id)
    )
    broker_count = int(broker_count_result.scalar_one() or 0)

    accessible_brokers_result = await session.execute(
        select(Broker.id, Broker.name)
        .join(BrokerUserAccess, BrokerUserAccess.broker_id == Broker.id)
        .where(BrokerUserAccess.user_id == token.user_id)
        .order_by(Broker.name.asc())
    )
    accessible_brokers = list(accessible_brokers_result.all())
    broker_name_by_id = {broker_id: broker_name for broker_id, broker_name in accessible_brokers}

    banking_details = []
    for broker_id, broker_name in accessible_brokers:
        cash_rows_result = await session.execute(
            select(Transaction.currency, func.sum(Transaction.amount))
            .where(Transaction.broker_id == broker_id)
            .where(Transaction.currency.is_not(None))
            .group_by(Transaction.currency)
            .order_by(Transaction.currency.asc())
        )
        cash_rows = [
            {"currency": currency, "amount": str(amount)}
            for currency, amount in cash_rows_result.all()
            if currency is not None and amount is not None
        ]
        banking_details.append(
            {
                "broker_id": broker_id,
                "broker_name": broker_name,
                "cash_balances": cash_rows,
            }
        )

    account_cash_totals_result = await session.execute(
        select(Transaction.currency, func.sum(Transaction.amount))
        .join(BrokerUserAccess, BrokerUserAccess.broker_id == Transaction.broker_id)
        .where(BrokerUserAccess.user_id == token.user_id)
        .where(Transaction.currency.is_not(None))
        .group_by(Transaction.currency)
        .order_by(Transaction.currency.asc())
    )
    account_cash_totals = [
        {"currency": currency, "amount": str(amount)}
        for currency, amount in account_cash_totals_result.all()
        if currency is not None and amount is not None
    ]

    holdings_result = await session.execute(
        select(
            Transaction.broker_id,
            Transaction.asset_id,
            Asset.display_name,
            Asset.currency,
            func.sum(Transaction.quantity),
        )
        .join(Asset, Asset.id == Transaction.asset_id)
        .join(BrokerUserAccess, BrokerUserAccess.broker_id == Transaction.broker_id)
        .where(BrokerUserAccess.user_id == token.user_id)
        .where(Transaction.asset_id.is_not(None))
        .group_by(Transaction.broker_id, Transaction.asset_id, Asset.display_name, Asset.currency)
        .order_by(Transaction.broker_id.asc(), Asset.display_name.asc())
    )
    asset_holdings = []
    for broker_id, asset_id, asset_name, asset_currency, quantity in holdings_result.all():
        if asset_id is None or quantity is None or quantity == 0:
            continue
        asset_holdings.append(
            {
                "broker_id": broker_id,
                "broker_name": broker_name_by_id.get(broker_id, f"Broker #{broker_id}"),
                "asset_id": int(asset_id),
                "asset_name": asset_name,
                "quantity": str(quantity),
                "asset_currency": asset_currency,
            }
        )

    threshold_value = 30
    threshold_unit = "days"
    last_activity_at = None
    if user_settings is not None:
        threshold_value = max(int(user_settings.nominee_threshold_days or 30), 1)
        threshold_unit = user_settings.nominee_threshold_unit or "days"
        last_activity_at = user_settings.last_activity_at

    return {
        "account_holder_username": user.username,
        "nominee_email": token.nominee_email,
        "access_scope": "read_only",
        "expires_at": ensure_utc(token.expires_at),
        "last_activity_at": ensure_utc(last_activity_at),
        "nominee_threshold_days": threshold_value,
        "nominee_threshold_unit": threshold_unit,
        "broker_count": broker_count,
        "broker_names": broker_names,
        "banking_details": banking_details,
        "account_cash_totals": account_cash_totals,
        "asset_holdings": asset_holdings,
    }
