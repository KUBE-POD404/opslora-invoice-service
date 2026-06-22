"""invoice engine v1

Revision ID: 20260506_invoice_0002
Revises: 20260501_invoice_0001
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa

revision = "20260506_invoice_0002"
down_revision = "20260501_invoice_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("invoice_number", sa.String(length=50), nullable=True))
    op.add_column("invoices", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.add_column("invoices", sa.Column("customer_name", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("customer_email", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("customer_gstin", sa.String(length=20), nullable=True))
    op.add_column("invoices", sa.Column("customer_place_of_supply", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("billing_address_line1", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("billing_address_line2", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("billing_city", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("billing_state", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("billing_postal_code", sa.String(length=30), nullable=True))
    op.add_column("invoices", sa.Column("billing_country", sa.String(length=100), nullable=True))

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("sku", sa.String(length=80), nullable=True),
        sa.Column("product_name", sa.String(length=150), nullable=False),
        sa.Column("hsn_sac_code", sa.String(length=20), nullable=True),
        sa.Column("unit_of_measure", sa.String(length=30), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoice_lines_id"), "invoice_lines", ["id"], unique=False)

    op.create_table(
        "invoice_tax_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoice_tax_summaries_id"), "invoice_tax_summaries", ["id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_invoice_tax_summaries_id"), table_name="invoice_tax_summaries")
    op.drop_table("invoice_tax_summaries")
    op.drop_index(op.f("ix_invoice_lines_id"), table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_column("invoices", "billing_country")
    op.drop_column("invoices", "billing_postal_code")
    op.drop_column("invoices", "billing_state")
    op.drop_column("invoices", "billing_city")
    op.drop_column("invoices", "billing_address_line2")
    op.drop_column("invoices", "billing_address_line1")
    op.drop_column("invoices", "customer_place_of_supply")
    op.drop_column("invoices", "customer_gstin")
    op.drop_column("invoices", "customer_email")
    op.drop_column("invoices", "customer_name")
    op.drop_column("invoices", "customer_id")
    op.drop_column("invoices", "invoice_number")
