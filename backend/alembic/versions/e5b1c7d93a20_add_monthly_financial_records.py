"""add monthly financial records

Research Enhancement Track, Phase B1 (docs/DECISIONS.md ADR-042). Creates
exactly one table, `monthly_financial_records`, and changes nothing else. It is
additive and separate from `financial_inputs`: that table stays the single
snapshot the goal and emergency-fund engines read, and no existing row is read,
rewritten or reinterpreted.

One row per customer per calendar month (`period_month` is the first day of the
month; unique with `customer_id`). Every amount is nullable -- NULL means "not
reported", never 0 -- and non-negative. `income_basis` ('net' or 'gross') may be
set only when an income is present, and a row must hold at least one amount.

Revision ID: e5b1c7d93a20
Revises: c3e8f2a9d154
Create Date: 2026-10-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b1c7d93a20"
down_revision: Union[str, None] = "c3e8f2a9d154"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monthly_financial_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("income", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("expenses", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("savings", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("investment_contribution", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("income_basis", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("extract(day from period_month) = 1", name="ck_monthly_records_period_first_of_month"),
        sa.CheckConstraint("income IS NULL OR income >= 0", name="ck_monthly_records_income_non_negative"),
        sa.CheckConstraint("expenses IS NULL OR expenses >= 0", name="ck_monthly_records_expenses_non_negative"),
        sa.CheckConstraint("savings IS NULL OR savings >= 0", name="ck_monthly_records_savings_non_negative"),
        sa.CheckConstraint(
            "investment_contribution IS NULL OR investment_contribution >= 0",
            name="ck_monthly_records_investment_non_negative",
        ),
        sa.CheckConstraint("income_basis IS NULL OR income_basis IN ('net', 'gross')", name="ck_monthly_records_income_basis"),
        sa.CheckConstraint("income_basis IS NULL OR income IS NOT NULL", name="ck_monthly_records_basis_needs_income"),
        sa.CheckConstraint(
            "income IS NOT NULL OR expenses IS NOT NULL OR savings IS NOT NULL OR investment_contribution IS NOT NULL",
            name="ck_monthly_records_has_an_amount",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "period_month", name="uq_monthly_records_customer_period"),
    )
    op.create_index(op.f("ix_monthly_financial_records_customer_id"), "monthly_financial_records", ["customer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_monthly_financial_records_customer_id"), table_name="monthly_financial_records")
    op.drop_table("monthly_financial_records")
