"""
Banking CSV preview API.

Provides CSV statement upload + expense/category/balance summary
without persisting data.
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.app.api.v1.auth import get_current_user
from backend.app.db.models import User

banking_router = APIRouter(prefix="/banking", tags=["Banking"])


class BankCategorySummary(BaseModel):
    category: str
    total_expense: Decimal


class BankStatementSummaryResponse(BaseModel):
    bank_name: str
    account_name: str
    rows_processed: int
    total_expense: Decimal
    total_income: Decimal
    net_change: Decimal
    current_balance: Decimal | None = None
    categories: list[BankCategorySummary] = Field(default_factory=list)


def _normalize_header(header: str) -> str:
    return "".join(ch for ch in header.lower().strip() if ch.isalnum())


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    cleaned = (
        text.replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("(", "-")
        .replace(")", "")
    )
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _find_column(headers: list[str], candidates: list[str]) -> str | None:
    normalized = {_normalize_header(h): h for h in headers}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


@banking_router.post("/statements/preview", response_model=BankStatementSummaryResponse)
async def preview_bank_statement(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(..., description="Bank statement in CSV format"),
    bank_name: str = "My Bank",
    account_name: str = "Primary Account",
) -> BankStatementSummaryResponse:
    _ = current_user
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    decoded = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            decoded = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded is None:
        raise HTTPException(status_code=400, detail="Unable to decode CSV file")

    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header row is missing")

    headers = reader.fieldnames
    amount_col = _find_column(headers, ["amount", "txnamount", "transactionamount", "value"])
    debit_col = _find_column(headers, ["debit", "withdrawal", "withdraw", "expense", "dr"])
    credit_col = _find_column(headers, ["credit", "deposit", "income", "cr"])
    balance_col = _find_column(headers, ["balance", "runningbalance", "closingbalance"])
    category_col = _find_column(headers, ["category", "type", "expensecategory", "merchantcategory"])

    if not any([amount_col, debit_col, credit_col]):
        raise HTTPException(
            status_code=400,
            detail="CSV must include one of: amount, debit, or credit column",
        )

    total_expense = Decimal("0")
    total_income = Decimal("0")
    current_balance: Decimal | None = None
    rows_processed = 0
    category_totals: dict[str, Decimal] = {}

    for row in reader:
        rows_processed += 1

        amount = _parse_decimal(row.get(amount_col)) if amount_col else None
        debit = _parse_decimal(row.get(debit_col)) if debit_col else None
        credit = _parse_decimal(row.get(credit_col)) if credit_col else None
        balance = _parse_decimal(row.get(balance_col)) if balance_col else None

        expense_value = Decimal("0")
        income_value = Decimal("0")

        if debit is not None:
            expense_value += abs(debit)
        if credit is not None:
            income_value += abs(credit)
        if amount is not None:
            if amount < 0:
                expense_value += abs(amount)
            elif amount > 0:
                income_value += amount

        total_expense += expense_value
        total_income += income_value

        if balance is not None:
            current_balance = balance

        if expense_value > 0:
            category = (row.get(category_col, "") if category_col else "").strip() or "Uncategorized"
            category_totals[category] = category_totals.get(category, Decimal("0")) + expense_value

    categories = [
        BankCategorySummary(category=key, total_expense=value)
        for key, value in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    return BankStatementSummaryResponse(
        bank_name=bank_name,
        account_name=account_name,
        rows_processed=rows_processed,
        total_expense=total_expense,
        total_income=total_income,
        net_change=total_income - total_expense,
        current_balance=current_balance,
        categories=categories,
    )
