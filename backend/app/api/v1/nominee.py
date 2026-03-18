"""Nominee access API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session_generator
from backend.app.schemas.nominee import NomineeAccessRead
from backend.app.services.nominee_access_service import (
    build_nominee_access_context,
    get_nominee_access_token,
    touch_nominee_access_token,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/nominee", tags=["Nominee"])


@router.get("/access", response_model=NomineeAccessRead)
async def get_nominee_access(
    token: str = Query(..., min_length=16, description="Nominee access token from the email link"),
    session: AsyncSession = Depends(get_session_generator),
) -> NomineeAccessRead:
    """Resolve a nominee token into a restricted read-only account summary."""
    token_row = await get_nominee_access_token(session, token)
    if token_row is None:
        raise HTTPException(status_code=401, detail="Nominee access link is invalid or expired")

    payload = await build_nominee_access_context(session, token_row)
    await touch_nominee_access_token(session, token_row)

    logger.info(
        "Nominee access granted",
        user_id=token_row.user_id,
        nominee_email=token_row.nominee_email,
    )
    return NomineeAccessRead(**payload)
