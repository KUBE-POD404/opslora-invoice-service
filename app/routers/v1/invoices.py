from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import InvoiceResponse, InvoiceStatusUpdate

from app.services.invoice_service import (
    create_invoice,
    get_invoice,
    list_invoices,
    cancel_invoice,
    update_invoice_status
)

from app.dependencies.permissions import require_permission

router = APIRouter(prefix="/invoices", tags=["Invoices"])


# -----------------------------
# HEALTH
# -----------------------------
@router.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------
# CREATE INVOICE
# -----------------------------
@router.post(
    "/orders/{order_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED
)
def create_invoice_api(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("invoice.create"))
):

    auth_header = request.headers.get("Authorization")

    return create_invoice(
        db=db,
        order_id=order_id,
        organization_id=current_user.org_id,
        created_by_user_id=current_user.user_id,
        auth_header=auth_header
    )


# -----------------------------
# GET INVOICE
# -----------------------------
@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice_api(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("invoice.read"))
):

    return get_invoice(
        db,
        invoice_id,
        current_user.org_id
    )


# -----------------------------
# LIST INVOICES
# -----------------------------
@router.get("/", response_model=list[InvoiceResponse])
def list_invoice_api(
    status: str | None = None,
    order_id: int | None = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("invoice.read"))
):

    return list_invoices(
        db,
        organization_id=current_user.org_id,
        status=status,
        order_id=order_id
    )


# -----------------------------
# CANCEL INVOICE
# -----------------------------
@router.post("/{invoice_id}/cancel", response_model=InvoiceResponse)
def cancel_invoice_api(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("invoice.cancel"))
):

    auth_header = request.headers.get("Authorization")

    return cancel_invoice(
        db,
        invoice_id,
        current_user.org_id,
        auth_header   
    )


# -----------------------------
# UPDATE STATUS
# -----------------------------
@router.post("/{invoice_id}/status")
def update_invoice_status_api(
    invoice_id: int,
    payload: InvoiceStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("invoice.update"))
):

    auth_header = request.headers.get("Authorization")

    return update_invoice_status(
        db,
        invoice_id,
        current_user.org_id,
        payload.status,
        auth_header   
    )