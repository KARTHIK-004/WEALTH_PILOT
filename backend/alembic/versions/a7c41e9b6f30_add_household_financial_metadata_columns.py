"""add household financial metadata columns

Phase 35. Additive only: it adds optional factual metadata to the four
household financial tables created in Phase 33 (migration d2be70d8b07f) and
changes nothing else.

- `notes` on all four tables: free text the household chooses to record.
- `description` on assets and liabilities, matching the optional
  `household_expenses.description` that already exists (`name` remains the
  short label on both).
- `interest_rate` on liabilities, `Numeric(6, 4)` to match the rate convention
  already used by `financial_inputs`, with a non-negative CHECK.

Every new column is NULLABLE, so existing rows are preserved untouched and no
backfill or default is applied -- an absent value stays "not provided", never 0
or an empty string (CLAUDE.md section 12).

Nothing here is read by any calculation: `core/household_finance.py` is
unchanged, and the Phase 34 financial summary is byte-identical for the same
records. In particular no debt ratio, amortization schedule, payoff date or
interest figure is computed from `interest_rate` (`docs/DECISIONS.md` ADR-034).

No existing column is removed, renamed or re-typed, and no existing constraint
is weakened: `amount > 0` and the nullable `monthly_payment` both stand
(ADR-032).

Revision ID: a7c41e9b6f30
Revises: d2be70d8b07f
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c41e9b6f30"
down_revision: Union[str, None] = "d2be70d8b07f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("household_incomes", sa.Column("notes", sa.String(length=500), nullable=True))

    op.add_column("household_expenses", sa.Column("notes", sa.String(length=500), nullable=True))

    op.add_column("household_assets", sa.Column("description", sa.String(length=200), nullable=True))
    op.add_column("household_assets", sa.Column("notes", sa.String(length=500), nullable=True))

    op.add_column("household_liabilities", sa.Column("interest_rate", sa.Numeric(precision=6, scale=4), nullable=True))
    op.add_column("household_liabilities", sa.Column("description", sa.String(length=200), nullable=True))
    op.add_column("household_liabilities", sa.Column("notes", sa.String(length=500), nullable=True))
    op.create_check_constraint(
        "ck_household_liabilities_interest_non_negative",
        "household_liabilities",
        "interest_rate IS NULL OR interest_rate >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_household_liabilities_interest_non_negative", "household_liabilities", type_="check")
    op.drop_column("household_liabilities", "notes")
    op.drop_column("household_liabilities", "description")
    op.drop_column("household_liabilities", "interest_rate")

    op.drop_column("household_assets", "notes")
    op.drop_column("household_assets", "description")

    op.drop_column("household_expenses", "notes")

    op.drop_column("household_incomes", "notes")
