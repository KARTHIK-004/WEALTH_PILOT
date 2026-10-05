"""add household goals

Phase 36. Creates exactly one table, `household_goals`, and changes nothing
else. A household goal belongs to a household through `household_id` alone and
is entirely separate from the individual `financial_goals` table, which is not
touched.

The table stores FACTS only: the household's name for the goal, a controlled
`goal_type`, its target amount and date, what it has already set aside
(`current_savings`, NULLABLE -- "not provided" is not 0), optional notes and the
Phase 33 `is_active` flag. No derived value is stored: no inflation-adjusted
target, no required contribution, no contribution gap, no feasibility and no
emergency-fund requirement (`docs/DECISIONS.md` ADR-035).

Revision ID: c3e8f2a9d154
Revises: a7c41e9b6f30
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e8f2a9d154"
down_revision: Union[str, None] = "a7c41e9b6f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "household_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("goal_type", sa.String(length=30), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("current_savings", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "goal_type IN ('emergency_fund', 'house', 'education', 'retirement', 'travel', 'major_purchase', 'other')",
            name="ck_household_goals_goal_type",
        ),
        sa.CheckConstraint("target_amount > 0", name="ck_household_goals_target_positive"),
        sa.CheckConstraint(
            "current_savings IS NULL OR current_savings >= 0", name="ck_household_goals_current_non_negative"
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_household_goals_name_not_blank"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_household_goals_household_id"), "household_goals", ["household_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_household_goals_household_id"), table_name="household_goals")
    op.drop_table("household_goals")
