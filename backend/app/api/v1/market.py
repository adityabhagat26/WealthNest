"""
Market data API endpoints backed by Yahoo Finance.
"""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from backend.app.db import IdentifierType
from backend.app.logging_config import get_logger
from backend.app.services.asset_source_providers.yahoo_finance import (
    YahooFinanceProvider,
    YFINANCE_AVAILABLE,
    yf,
)

logger = get_logger(__name__)

market_router = APIRouter(prefix="/market", tags=["Market Data"])


def _normalize_symbol_for_nse(symbol: str) -> str:
    """
    Normalize symbol for Indian NSE by default.
    If user already passes market suffix/pair (e.g. .NS, -USD), keep as-is.
    """
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("Symbol cannot be empty")
    if "." in cleaned or "-" in cleaned:
        return cleaned
    return f"{cleaned}.NS"


@market_router.get("/yahoo/quote/{symbol}")
async def get_yahoo_quote(symbol: str):
    """
    Fetch latest quote for a symbol from Yahoo Finance.
    """
    try:
        provider = YahooFinanceProvider()
        resolved_symbol = _normalize_symbol_for_nse(symbol)
        current = await provider.get_current_value(
            identifier=resolved_symbol,
            identifier_type=IdentifierType.TICKER,
            provider_params=None,
        )
        return {
            "symbol": resolved_symbol,
            "regular_market_price": float(current.value),
            "currency": current.currency or "INR",
            "as_of_date": current.as_of_date.isoformat(),
            "source": current.source,
        }
    except Exception as exc:
        logger.error("Yahoo quote fetch failed", symbol=symbol, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch stock quote")


@market_router.get("/yahoo/history/{symbol}")
async def get_yahoo_history(
    symbol: str,
    period_days: int = Query(90, ge=7, le=730, description="Number of days back from today"),
):
    """
    Fetch historical close prices for a symbol from Yahoo Finance.
    """
    try:
        provider = YahooFinanceProvider()
        resolved_symbol = _normalize_symbol_for_nse(symbol)
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        try:
            history = await provider.get_history_value(
                identifier=resolved_symbol,
                identifier_type=IdentifierType.TICKER,
                provider_params=None,
                start_date=start_date,
                end_date=end_date,
            )
            points = [
                {
                    "date": p.date.isoformat(),
                    "close": float(p.close),
                }
                for p in history.prices
                if p.close is not None
            ]
            if points:
                return {
                    "symbol": resolved_symbol,
                    "currency": history.currency or "INR",
                    "points": points,
                    "source": history.source,
                }
        except Exception:
            # Fall back to period-based history query, which is often more robust
            # when local system date/time and market timezone boundaries differ.
            pass

        if not YFINANCE_AVAILABLE or yf is None:
            raise RuntimeError("yfinance library unavailable")

        ticker = yf.Ticker(resolved_symbol)
        hist_df = ticker.history(period=f"{period_days}d")
        if hist_df.empty:
            return {
                "symbol": resolved_symbol,
                "currency": "INR",
                "points": [],
                "source": "Yahoo Finance",
            }

        points = [
            {
                "date": idx.date().isoformat(),
                "close": float(row["Close"]),
            }
            for idx, row in hist_df.iterrows()
            if row.get("Close") is not None
        ]
        currency = None
        try:
            currency = ticker.fast_info.get("currency")
        except Exception:
            currency = "INR"

        return {
            "symbol": resolved_symbol,
            "currency": currency or "INR",
            "points": points,
            "source": "Yahoo Finance",
        }
    except Exception as exc:
        logger.error("Yahoo history fetch failed", symbol=symbol, error=str(exc))
        return {
            "symbol": _normalize_symbol_for_nse(symbol),
            "currency": "INR",
            "points": [],
            "source": "Yahoo Finance",
        }
