"""
Nominee inactivity notification service.

This module is intentionally self-contained so the feature is easy to share
or port into another project.
"""

import asyncio
import smtplib
from datetime import timedelta, timezone
from email.message import EmailMessage

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.models import User, UserSettings
from backend.app.db.session import get_async_engine
from backend.app.services.nominee_access_service import create_nominee_access_link
from backend.app.utils.datetime_utils import utcnow

logger = structlog.get_logger(__name__)

ALLOWED_THRESHOLD_UNITS = {"days", "hours", "minutes", "seconds"}
ACTIVITY_TOUCH_MIN_INTERVAL = timedelta(seconds=5)
ACTIVITY_TOUCH_MAX_INTERVAL = timedelta(minutes=15)


def normalize_utc_datetime(value):
    """Normalize DB-loaded datetimes to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def nominee_email_configured() -> bool:
    """Return True when SMTP settings are present enough to send mail."""
    settings = get_settings()
    return bool(settings.SMTP_HOST and settings.NOMINEE_EMAIL_FROM)


def get_threshold_unit(settings_row: UserSettings) -> str:
    """Return a safe threshold unit."""
    unit = getattr(settings_row, "nominee_threshold_unit", "days") or "days"
    return unit if unit in ALLOWED_THRESHOLD_UNITS else "days"


def build_threshold_delta(threshold_value: int, threshold_unit: str) -> timedelta:
    """Convert the stored threshold into a timedelta."""
    safe_value = max(int(threshold_value or 1), 1)
    safe_unit = threshold_unit if threshold_unit in ALLOWED_THRESHOLD_UNITS else "days"
    return timedelta(**{safe_unit: safe_value})


def format_threshold_label(threshold_value: int, threshold_unit: str) -> str:
    """Human-readable threshold label."""
    safe_unit = threshold_unit if threshold_unit in ALLOWED_THRESHOLD_UNITS else "days"
    safe_value = max(int(threshold_value or 1), 1)
    if safe_value == 1 and safe_unit.endswith("s"):
        safe_unit = safe_unit[:-1]
    return f"{safe_value} {safe_unit}"


def format_duration_label(duration: timedelta) -> str:
    """Human-readable duration for email content and logs."""
    total_seconds = max(int(duration.total_seconds()), 0)
    if total_seconds < 60:
        value, unit = total_seconds, "second"
    elif total_seconds < 3600:
        value, unit = total_seconds // 60, "minute"
    elif total_seconds < 86400:
        value, unit = total_seconds // 3600, "hour"
    else:
        value, unit = total_seconds // 86400, "day"
    return f"{value} {unit}{'' if value == 1 else 's'}"


def build_nominee_email(
    user: User,
    nominee_email: str,
    threshold_value: int,
    threshold_unit: str,
    inactive_duration: timedelta,
    access_url: str | None = None,
) -> EmailMessage:
    """Create the inactivity notification email."""
    settings = get_settings()
    from_address = settings.NOMINEE_EMAIL_FROM or settings.SMTP_USERNAME
    threshold_label = format_threshold_label(threshold_value, threshold_unit)
    inactive_label = format_duration_label(inactive_duration)

    message = EmailMessage()
    message["Subject"] = f"WealthNest account inactivity notification for {user.username}"
    message["From"] = from_address
    message["To"] = nominee_email
    message.set_content(
        "\n".join(
            [
                f"Hello,",
                "",
                f"This is an automated notification from WealthNest concerning the account of {user.username}.",
                "",
                f"We have not detected any authenticated activity for {inactive_label}. This exceeds the configured inactivity threshold of {threshold_label}.",
                "",
                "If this is expected, no further action is needed.",
                "",
                "If this is unexpected, please reach out to the account holder directly to verify the situation.",
                *(
                    [
                        "",
                        "If you need read-only nominee access, please use the secure link below before it expires:",
                        access_url,
                    ]
                    if access_url
                    else []
                ),
                "",
                "Kind regards,",
                "WealthNest",
                "Automated Notification Service",
            ]
        )
    )
    return message


def build_nominee_added_email(user: User, nominee_email: str) -> EmailMessage:
    """Create the nominee contact confirmation email."""
    settings = get_settings()
    from_address = settings.NOMINEE_EMAIL_FROM or settings.SMTP_USERNAME

    message = EmailMessage()
    message["Subject"] = f"You have been added as a nominee contact for {user.username} on WealthNest"
    message["From"] = from_address
    message["To"] = nominee_email
    message.set_content(
        "\n".join(
            [
                "Hello,",
                "",
                "This is an automated notification from WealthNest.",
                "",
                f"You have been added as the nominee contact for the WealthNest account of {user.username}. This means you may receive an email notification in the future if the account remains inactive beyond the configured threshold.",
                "",
                "No action is required from you at this time.",
                "",
                "If you were expecting this, you can simply keep this email for your reference.",
                "",
                f"If you were not expecting this, or you believe your email address was added by mistake, please contact {user.username} directly to confirm the details.",
                "",
                "Kind regards,",
                "WealthNest",
                "Automated Notification Service",
            ]
        )
    )
    return message


def send_nominee_email(
    user: User,
    nominee_email: str,
    threshold_value: int,
    threshold_unit: str,
    inactive_duration: timedelta,
    access_url: str | None = None,
) -> None:
    """Send the inactivity email using SMTP settings from the environment."""
    settings = get_settings()
    if not nominee_email_configured():
        raise RuntimeError("Nominee email is not configured. Set SMTP_HOST and NOMINEE_EMAIL_FROM.")

    message = build_nominee_email(
        user,
        nominee_email,
        threshold_value,
        threshold_unit,
        inactive_duration,
        access_url,
    )

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


def send_nominee_added_email(user: User, nominee_email: str) -> None:
    """Send the nominee contact confirmation email using SMTP settings from the environment."""
    settings = get_settings()
    if not nominee_email_configured():
        raise RuntimeError("Nominee email is not configured. Set SMTP_HOST and NOMINEE_EMAIL_FROM.")

    message = build_nominee_added_email(user, nominee_email)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


async def ensure_user_settings(session: AsyncSession, user_id: int) -> UserSettings:
    """Get or create UserSettings for nominee/activity tracking."""
    result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings_row = result.scalar_one_or_none()

    if settings_row is None:
        now = utcnow()
        settings_row = UserSettings(
            user_id=user_id,
            language="en",
            base_currency="INR",
            theme="light",
            nominee_enabled=False,
            nominee_threshold_days=30,
            nominee_threshold_unit="days",
            last_activity_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(settings_row)
        await session.commit()
        await session.refresh(settings_row)

    return settings_row


async def touch_user_activity(session: AsyncSession, user_id: int) -> None:
    """Refresh last_activity_at with throttling to avoid a DB write on every request."""
    settings_row = await ensure_user_settings(session, user_id)
    now = utcnow()
    last_activity_at = normalize_utc_datetime(settings_row.last_activity_at)
    threshold_delta = build_threshold_delta(
        settings_row.nominee_threshold_days,
        get_threshold_unit(settings_row),
    )
    touch_interval = min(
        ACTIVITY_TOUCH_MAX_INTERVAL,
        max(ACTIVITY_TOUCH_MIN_INTERVAL, threshold_delta / 2),
    )

    if last_activity_at and now - last_activity_at < touch_interval:
        return

    settings_row.last_activity_at = now
    settings_row.updated_at = now
    settings_row.nominee_last_notified_at = None
    session.add(settings_row)
    await session.commit()


async def process_nominee_notifications(session: AsyncSession) -> int:
    """Send inactivity emails for all users who crossed their threshold."""
    result = await session.execute(
        select(UserSettings, User).join(User, User.id == UserSettings.user_id).where(
            UserSettings.nominee_enabled.is_(True),
            UserSettings.nominee_email.is_not(None),
            User.is_active.is_(True),
        )
    )
    rows = result.all()
    now = utcnow()
    sent_count = 0

    for settings_row, user in rows:
        last_activity = normalize_utc_datetime(settings_row.last_activity_at) or normalize_utc_datetime(
            settings_row.created_at
        ) or now
        inactive_duration = now - last_activity
        threshold_unit = get_threshold_unit(settings_row)
        threshold_value = max(int(settings_row.nominee_threshold_days or 1), 1)
        threshold_delta = build_threshold_delta(threshold_value, threshold_unit)

        if inactive_duration < threshold_delta:
            continue

        last_notified_at = normalize_utc_datetime(settings_row.nominee_last_notified_at)
        if last_notified_at and last_notified_at >= last_activity:
            continue

        try:
            access_url = await create_nominee_access_link(session, user, settings_row.nominee_email)
            send_nominee_email(
                user,
                settings_row.nominee_email,
                threshold_value,
                threshold_unit,
                inactive_duration,
                access_url=access_url,
            )
            settings_row.nominee_last_notified_at = now
            settings_row.updated_at = now
            session.add(settings_row)
            sent_count += 1
            logger.info(
                "Nominee inactivity email sent",
                user_id=user.id,
                nominee_email=settings_row.nominee_email,
                inactive_for=format_duration_label(inactive_duration),
                threshold=format_threshold_label(threshold_value, threshold_unit),
            )
        except Exception as exc:
            logger.error(
                "Failed to send nominee inactivity email",
                user_id=user.id,
                nominee_email=settings_row.nominee_email,
                error=str(exc),
            )

    if sent_count:
        await session.commit()

    return sent_count


async def nominee_monitor_loop(stop_event: asyncio.Event) -> None:
    """Periodic background loop that checks inactive users and emails nominees."""
    settings = get_settings()
    interval_seconds = settings.NOMINEE_CHECK_INTERVAL_SECONDS
    if interval_seconds <= 0:
        interval_seconds = max(settings.NOMINEE_CHECK_INTERVAL_MINUTES, 1) * 60
    logger.info("Nominee monitor started", interval_seconds=interval_seconds)

    while not stop_event.is_set():
        try:
            async with AsyncSession(get_async_engine(), expire_on_commit=False) as session:
                await process_nominee_notifications(session)
        except Exception as exc:
            logger.error("Nominee monitor iteration failed", error=str(exc))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue

    logger.info("Nominee monitor stopped")
