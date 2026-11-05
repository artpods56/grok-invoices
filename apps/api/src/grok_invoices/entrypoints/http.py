import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastmcp.utilities.lifespan import combine_lifespans

from grok_invoices.domain.errors import Conflict, DomainError, Invalid, KsefUnavailable, NotFound
from grok_invoices.domain.models import Account, Case, CaseStatus, Event, InvoiceStatus, Posting, Question, QuestionStatus
from grok_invoices.entrypoints.mcp import client_mcp_app
from grok_invoices.entrypoints.mcp_agents import invoices_app, regulations_app
from grok_invoices.service_layer import commands, services
from grok_invoices.service_layer.views import (
    CaseDetail, ClientProfile, InvoiceDetail, InvoiceSummary, IssuedInvoice, PrecedentMatch,
)
from grok_invoices.settings import get_settings

_STATUS_BY_ERROR = {NotFound: 404, Conflict: 409, Invalid: 422, KsefUnavailable: 502}


def require_api_key(request: Request, authorization: str | None = Header(default=None)) -> None:
    """Writes need the key because this API is public. Reads hold only demo data."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    key = get_settings().platform_api_key
    if not key:
        return  # Local development only: the app won't start deployed without a key.
    if not hmac.compare_digest((authorization or "").encode(), f"Bearer {key}".encode()):
        raise HTTPException(401, "Missing or invalid API key", headers={"WWW-Authenticate": "Bearer"})


router = APIRouter(prefix="/api", dependencies=[Depends(require_api_key)])


@router.get("/client", response_model=ClientProfile, tags=["client"])
def get_client():
    return services.get_client()


@router.post("/client/facts", response_model=ClientProfile, status_code=201, tags=["client"])
def add_fact(body: commands.AddFact):
    return services.add_fact(body)


@router.put("/client/vehicles", response_model=ClientProfile, tags=["client"])
def save_vehicle(body: commands.SaveVehicle):
    return services.save_vehicle(body)


@router.get("/accounts", response_model=list[Account], tags=["client"])
def list_accounts():
    return services.list_accounts()


@router.get("/invoices", response_model=list[InvoiceSummary], tags=["invoices"])
def list_invoices(status: InvoiceStatus | None = None):
    return services.list_invoices(status)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail, tags=["invoices"])
def get_invoice(invoice_id: int):
    return services.get_invoice(invoice_id)


@router.get("/invoices/{invoice_id}/xml", tags=["invoices"])
def get_invoice_xml(invoice_id: int) -> Response:
    """The FA(3) XML exactly as KSeF delivered it."""
    return Response(services.get_invoice_xml(invoice_id), media_type="application/xml")


@router.get("/invoices/{invoice_id}/precedents", response_model=list[PrecedentMatch], tags=["invoices"])
def search_precedents(invoice_id: int):
    """Find past decisions similar to this invoice, best match first."""
    return services.search_precedents(invoice_id)


@router.post("/invoices/{invoice_id}/postings", response_model=Posting, status_code=201, tags=["invoices"])
def post_invoice(invoice_id: int, body: commands.PostInvoice):
    return services.post_invoice(invoice_id, body)


@router.post("/invoices/{invoice_id}/escalate", response_model=CaseDetail, status_code=201, tags=["cases"])
def escalate_invoice(invoice_id: int, body: commands.Escalate):
    return services.escalate_invoice(invoice_id, body)


@router.post("/postings/{posting_id}/correct", response_model=Posting, status_code=201, tags=["accountant"])
def correct_posting(posting_id: int, body: commands.CorrectPosting):
    return services.correct_posting(posting_id, body)


@router.get("/cases", response_model=list[Case], tags=["cases"])
def list_cases(status: CaseStatus | None = None):
    return services.list_cases(status)


@router.get("/cases/{case_id}", response_model=CaseDetail, tags=["cases"])
def get_case(case_id: int):
    return services.get_case(case_id)


@router.post("/cases/{case_id}/questions", response_model=Question, status_code=201, tags=["cases"])
def ask_client(case_id: int, body: commands.AskClient):
    return services.ask_client(case_id, body)


@router.post("/cases/{case_id}/take-over", response_model=CaseDetail, tags=["accountant"])
def take_over_case(case_id: int):
    return services.take_over_case(case_id)


@router.get("/questions", response_model=list[Question], tags=["cases"])
def list_questions(status: QuestionStatus | None = None):
    return services.list_questions(status)


@router.post("/questions/{question_id}/answer", response_model=Question, tags=["cases"])
def answer_question(question_id: int, body: commands.AnswerQuestion):
    return services.answer_question(question_id, body)


@router.get("/events", response_model=list[Event], tags=["timeline"])
def list_events(after: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=1000)):
    """The timeline, oldest first. Pass the last seen id as `after` to poll for new events."""
    return services.list_events(after, limit)


@router.post("/ksef/sync", response_model=list[InvoiceSummary], tags=["invoices"])
def sync_ksef(source: services.KsefSource = "test"):
    """Fetch new purchase invoices from KSeF TEST, or the sample fixtures where SAMPLE_DATA is set."""
    return services.sync_ksef(source)


@router.post("/demo/issue-fuel-invoice", response_model=IssuedInvoice, status_code=201, tags=["demo"])
def issue_demo_invoice():
    """Issue the stage demo's fuel invoice on KSeF TEST. Then sync with `source=test`."""
    return services.issue_demo_invoice()


@router.post("/demo/reset", status_code=204, tags=["demo"])
def reset_demo() -> None:
    """Restore the seed data so the demo can run again."""
    services.reset_demo()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Failing here makes a deploy without the key roll back instead of exposing writes.
    if settings.release and not settings.platform_api_key:
        raise RuntimeError("PLATFORM_API_KEY must be set when deployed")
    services.start_platform()
    yield


app = FastAPI(
    title="Grok Invoices",
    version="0.1.0",
    lifespan=combine_lifespans(lifespan, client_mcp_app.lifespan, invoices_app.lifespan, regulations_app.lifespan),
)
app.include_router(router)
app.mount("/agents/client", client_mcp_app)
app.mount("/agents/invoices", invoices_app)
app.mount("/agents/regulations", regulations_app)


@app.exception_handler(DomainError)
async def report_domain_error(_: Request, error: DomainError) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=_STATUS_BY_ERROR.get(type(error), 400))


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Welcome to Grok Invoices"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
