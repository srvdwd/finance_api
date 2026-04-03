from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType


def get_summary(db: Session) -> dict:
    """Total income, expenses, balance, and counts."""
    rows = (
        db.query(
            Transaction.type,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .group_by(Transaction.type)
        .all()
    )

    total_income = 0.0
    total_expenses = 0.0
    income_count = 0
    expense_count = 0

    for row in rows:
        if row.type == TransactionType.income:
            total_income = round(row.total or 0, 2)
            income_count = row.count
        elif row.type == TransactionType.expense:
            total_expenses = round(row.total or 0, 2)
            expense_count = row.count

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": round(total_income - total_expenses, 2),
        "income_count": income_count,
        "expense_count": expense_count,
        "total_transactions": income_count + expense_count,
    }


def get_by_category(db: Session, type: Optional[str] = None) -> list[dict]:
    """Spending/earning breakdown grouped by category."""
    query = db.query(
        Transaction.category,
        Transaction.type,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count"),
    ).group_by(Transaction.category, Transaction.type)

    if type:
        query = query.filter(Transaction.type == type)

    rows = query.order_by(func.sum(Transaction.amount).desc()).all()

    return [
        {
            "category": row.category,
            "type": row.type,
            "total": round(row.total or 0, 2),
            "count": row.count,
        }
        for row in rows
    ]


def get_monthly_totals(db: Session, year: Optional[int] = None) -> list[dict]:
    """Month-by-month income and expense totals, optionally filtered by year."""
    # func.strftime is SQLite-compatible; swap for func.date_trunc on Postgres
    month_expr = func.strftime("%Y-%m", Transaction.date)

    query = db.query(
        month_expr.label("month"),
        Transaction.type,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count"),
    ).group_by(month_expr, Transaction.type)

    if year:
        query = query.filter(func.strftime("%Y", Transaction.date) == str(year))

    rows = query.order_by(month_expr.asc()).all()

    # Pivot into {month: {income, expense, balance}}
    monthly: dict[str, dict] = {}
    for row in rows:
        m = row.month
        if m not in monthly:
            monthly[m] = {"month": m, "income": 0.0, "expense": 0.0, "balance": 0.0, "count": 0}
        monthly[m][row.type.value] = round(row.total or 0, 2)
        monthly[m]["count"] += row.count

    for m in monthly:
        monthly[m]["balance"] = round(monthly[m]["income"] - monthly[m]["expense"], 2)

    return sorted(monthly.values(), key=lambda x: x["month"])


def get_recent_transactions(db: Session, limit: int = 10) -> list[Transaction]:
    """Most recent N transactions ordered by date."""
    return (
        db.query(Transaction)
        .order_by(Transaction.date.desc())
        .limit(limit)
        .all()
    )
