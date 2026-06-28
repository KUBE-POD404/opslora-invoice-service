# Backend invoice PDF generation

Timestamp: 20260628-103904Z
Repo: opslora-invoice-service
Branch: feat/backend-invoice-pdf

## Why

The previous invoice Download action produced browser-generated printable HTML. In browser print/save-as-PDF, the document was over-spaced and could cut content. User requested real backend PDF generation and verified the issue on test invoice `/invoices/2`.

## Root cause

The invoice-service exposed invoice JSON and template metadata, but no binary PDF endpoint. The frontend had to generate a large HTML document and rely on browser print behavior, which made spacing/page-fit inconsistent.

## Changes

- Added production dependency `reportlab`.
- Added dev test dependency `pypdf`.
- Added optional config `PAYMENT_SERVICE_URL`.
- Added `app/services/invoice_pdf.py`:
  - compact ReportLab A4 PDF generation
  - Opslora default invoice styling
  - invoice header with invoice number, order id, status, issued/due dates
  - seller and bill-to sections
  - compact line-item table
  - tax summary table
  - totals, paid amount, and balance due
  - terms/footer
  - payment transactions from payment-service when configured
  - graceful fallback text if payment-service lookup fails
- Added `GET /api/v1/invoices/{invoice_id}/download`:
  - tenant-scoped through existing `invoice.read` permission
  - returns `application/pdf`
  - sets attachment filename `<invoice-number>-opslora-invoice.pdf`

## Tests

Added `tests/test_invoice_pdf_download.py`.

Regression coverage:

- endpoint returns HTTP 200 and `application/pdf`
- response starts with `%PDF`
- content-disposition is an attachment using the invoice number
- extracted PDF text includes live invoice number, order id, customer, product, total, and payment reference
- invoice #2-like simple invoice fits in one PDF page
- if payment-service lookup fails, PDF still returns and includes `Payment transactions unavailable`

## Validation

From `/tmp/opslora-invoice-pdf-backend`:

```bash
uv venv .venv
. .venv/bin/activate
uv pip install -r requirements-dev.txt
pytest -q --cov=app --cov-report=xml
```

Result:

```text
16 passed, 1 warning
Coverage XML written to file coverage.xml
```

## Deployment notes

The service defaults `PAYMENT_SERVICE_URL` to blank, so the endpoint works even before Helm passes payment-service URL. For Azure test, Helm should set:

```yaml
PAYMENT_SERVICE_URL: http://payment-service:3000
```

That Helm change is staged separately in `/tmp/opslora-helm-invoice-pdf`.
