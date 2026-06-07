"""invoice seller settings snapshot

Revision ID: 20260607_invoice_0004
Revises: 20260506_invoice_0003
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

revision = "20260607_invoice_0004"
down_revision = "20260506_invoice_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("seller_legal_name", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("seller_display_name", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("seller_email", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("seller_phone", sa.String(length=50), nullable=True))
    op.add_column("invoices", sa.Column("seller_tax_id", sa.String(length=50), nullable=True))
    op.add_column("invoices", sa.Column("seller_address", sa.String(length=500), nullable=True))
    op.add_column("invoices", sa.Column("seller_country", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("invoice_terms", sa.String(length=1000), nullable=True))
    op.add_column("invoices", sa.Column("invoice_footer", sa.String(length=1000), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("round_off_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("invoices", "round_off_enabled", server_default=None)


def downgrade():
    op.drop_column("invoices", "round_off_enabled")
    op.drop_column("invoices", "invoice_footer")
    op.drop_column("invoices", "invoice_terms")
    op.drop_column("invoices", "seller_country")
    op.drop_column("invoices", "seller_address")
    op.drop_column("invoices", "seller_tax_id")
    op.drop_column("invoices", "seller_phone")
    op.drop_column("invoices", "seller_email")
    op.drop_column("invoices", "seller_display_name")
    op.drop_column("invoices", "seller_legal_name")
