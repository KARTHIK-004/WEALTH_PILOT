"""add protected records and audit ledger

Sensitive Data Protection prototype (docs/DECISIONS.md ADR-047). Creates exactly two new tables and changes nothing
else; no existing table, column or row is read, rewritten, encrypted or reinterpreted.

- `protected_records`: a customer-written private note stored only as an AES-256-GCM envelope (nonce, ciphertext+tag,
  algorithm, envelope version, non-secret key id). There is no plaintext column.
- `audit_ledger_events`: the LOCAL hash-chained audit log (academic prototype, not a blockchain). Unique `sequence`
  (primary key), `prev_hash` and `event_hash` make a concurrent fork fail instead of silently succeeding.

Rollback: `alembic downgrade e5b1c7d93a20` drops both tables. Doing so destroys the encrypted notes and the audit
chain; there is nothing else to restore because no existing data was touched.

Revision ID: f7a2d4b6c810
Revises: e5b1c7d93a20
Create Date: 2026-10-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a2d4b6c810"
down_revision: Union[str, None] = "e5b1c7d93a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "protected_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False),
        sa.Column("envelope_version", sa.Integer(), nullable=False),
        sa.Column("algorithm", sa.String(length=20), nullable=False),
        sa.Column("key_id", sa.String(length=32), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_protected_records_customer_id"), "protected_records", ["customer_id"], unique=False)

    op.create_table(
        "audit_ledger_events",
        sa.Column("sequence", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_ref", sa.String(length=36), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("sequence"),
        sa.UniqueConstraint("prev_hash"),
        sa.UniqueConstraint("event_hash"),
    )


def downgrade() -> None:
    op.drop_table("audit_ledger_events")
    op.drop_index(op.f("ix_protected_records_customer_id"), table_name="protected_records")
    op.drop_table("protected_records")
