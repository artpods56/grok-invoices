import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app import seed, store
from app.db import read, transaction
from app.schemas import (
    Account, AnswerIn, Case, CaseDetail, CaseStatus, Client, CorrectionIn, EscalationIn, Event, FactIn, Invoice,
    InvoiceDetail, InvoiceIn, InvoiceStatus, Posting, PostingIn, PrecedentMatch, Question, QuestionIn, QuestionStatus,
    VehicleIn,
)


def require_api_key(request: Request, authorization: str | None = Header(default=None)) -> None:
    """Writes need the key because this API is public. Reads hold only demo data."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    key = os.environ.get("PLATFORM_API_KEY")
    if not key:
        return  # Local development only: the app won't start deployed without a key.
    if not hmac.compare_digest((authorization or "").encode(), f"Bearer {key}".encode()):
        raise HTTPException(401, "Missing or invalid API key", headers={"WWW-Authenticate": "Bearer"})


router = APIRouter(prefix="/api", dependencies=[Depends(require_api_key)])


@router.get("/client", response_model=Client, tags=["client"])
def get_client():
    with read() as conn:
        return store.get_client(conn)


@router.post("/client/facts", response_model=Client, status_code=201, tags=["client"])
def add_fact(body: FactIn):
    with transaction() as conn:
        return store.add_fact(conn, body)


@router.put("/client/vehicles", response_model=Client, tags=["client"])
def save_vehicle(body: VehicleIn):
    with transaction() as conn:
        return store.add_vehicle(conn, body)


@router.get("/accounts", response_model=list[Account], tags=["client"])
def list_accounts():
    with read() as conn:
        return store.list_accounts(conn)


@router.get("/invoices", response_model=list[Invoice], tags=["invoices"])
def list_invoices(status: InvoiceStatus | None = None):
    with read() as conn:
        return store.list_invoices(conn, status)


@router.post("/invoices", response_model=Invoice, status_code=201, tags=["invoices"])
def create_invoice(body: InvoiceIn):
    with transaction() as conn:
        return store.insert_invoice(conn, body)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail, tags=["invoices"])
def get_invoice(invoice_id: int):
    with read() as conn:
        return store.get_invoice(conn, invoice_id)


@router.get("/invoices/{invoice_id}/precedents", response_model=list[PrecedentMatch], tags=["invoices"])
def search_precedents(invoice_id: int):
    """Find past decisions similar to this invoice, best match first."""
    with read() as conn:
        return store.search_precedents(conn, invoice_id)


@router.post("/invoices/{invoice_id}/postings", response_model=Posting, status_code=201, tags=["invoices"])
def create_posting(invoice_id: int, body: PostingIn):
    with transaction() as conn:
        return store.create_posting(conn, invoice_id, body)


@router.post("/invoices/{invoice_id}/escalate", response_model=CaseDetail, status_code=201, tags=["cases"])
def escalate_invoice(invoice_id: int, body: EscalationIn):
    with transaction() as conn:
        return store.escalate_invoice(conn, invoice_id, body)


@router.post("/postings/{posting_id}/correct", response_model=Posting, status_code=201, tags=["accountant"])
def correct_posting(posting_id: int, body: CorrectionIn):
    with transaction() as conn:
        return store.correct_posting(conn, posting_id, body)


@router.get("/cases", response_model=list[Case], tags=["cases"])
def list_cases(status: CaseStatus | None = None):
    with read() as conn:
        return store.list_cases(conn, status)


@router.get("/cases/{case_id}", response_model=CaseDetail, tags=["cases"])
def get_case(case_id: int):
    with read() as conn:
        return store.get_case(conn, case_id)


@router.post("/cases/{case_id}/questions", response_model=Question, status_code=201, tags=["cases"])
def ask_question(case_id: int, body: QuestionIn):
    with transaction() as conn:
        return store.ask_question(conn, case_id, body)


@router.post("/cases/{case_id}/take-over", response_model=CaseDetail, tags=["accountant"])
def take_over_case(case_id: int):
    with transaction() as conn:
        return store.take_over_case(conn, case_id)


@router.get("/questions", response_model=list[Question], tags=["cases"])
def list_questions(status: QuestionStatus | None = None):
    with read() as conn:
        return store.list_questions(conn, status)


@router.post("/questions/{question_id}/answer", response_model=Question, tags=["cases"])
def answer_question(question_id: int, body: AnswerIn):
    with transaction() as conn:
        return store.answer_question(conn, question_id, body)


@router.get("/events", response_model=list[Event], tags=["timeline"])
def list_events(after: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=1000)):
    """The timeline, oldest first. Pass the last seen id as `after` to poll for new events."""
    with read() as conn:
        return store.list_events(conn, after, limit)


@router.post("/ksef/sync", response_model=list[Invoice], tags=["invoices"])
def sync_ksef():
    """Fetch new purchase invoices. Uses the mock inbox until the real KSeF integration exists."""
    with transaction() as conn:
        return seed.sync_mock_ksef(conn)


@router.post("/demo/reset", status_code=204, tags=["demo"])
def reset_demo() -> None:
    """Restore the seed data so the demo can run again."""
    with transaction() as conn:
        seed.reset(conn)
