"""invoice baseline

Revision ID: 20260501_invoice_0001
Revises:
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260501_invoice_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("tax", sa.Numeric(10, 2), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_type", sa.String(length=10), nullable=True),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('UNPAID','PARTIALLY_PAID','PAID','OVERDUE','CANCELLED','REFUNDED')",
            name="check_invoice_status",
        ),
        sa.CheckConstraint("discount_type IN ('FLAT','PERCENT')", name="check_discount_type"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(op.f("ix_invoices_id"), "invoices", ["id"], unique=False)
    op.create_index(op.f("ix_invoices_organization_id"), "invoices", ["organization_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_invoices_organization_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_id"), table_name="invoices")
    op.drop_table("invoices")
