"""invoice settings tax components

Revision ID: 20260506_invoice_0003
Revises: 20260506_invoice_0002
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa

revision = "20260506_invoice_0003"
down_revision = "20260506_invoice_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("invoice_template_key", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("seller_state", sa.String(length=100), nullable=True))
    op.add_column(
        "invoice_tax_summaries",
        sa.Column("tax_component", sa.String(length=20), nullable=False, server_default="IGST"),
    )


def downgrade():
    op.drop_column("invoice_tax_summaries", "tax_component")
    op.drop_column("invoices", "seller_state")
    op.drop_column("invoices", "invoice_template_key")
