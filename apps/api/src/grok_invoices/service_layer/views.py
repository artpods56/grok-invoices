"""What services return. Fields are read straight from the domain models' attributes."""

from datetime import date, datetime
from decimal import Decimal

from ksef2.fa3 import KsefInvoice
from pydantic import BaseModel, ConfigDict, Field

from grok_invoices.domain.models import Account, Case, Fact, InvoiceStatus, Posting, Question, Vehicle


class View(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClientProfile(View):
    """What's safe to return about the client. Reads are public, so contact details and secrets stay out."""

    name: str
    nip: str
    fleet: list[Vehicle]
    facts: list[Fact]
    accounts: list[Account]


class InvoiceSummary(View):
    id: int
    ksef_number: str
    invoice_number: str
    seller_name: str
    seller_nip: str
    description: str
    vehicle_plate: str | None
    net: Decimal
    vat: Decimal
    gross: Decimal
    issue_date: date
    status: InvoiceStatus
    received_at: datetime


class InvoiceDetail(InvoiceSummary):
    document: KsefInvoice = Field(description="The full FA(3) invoice, as ksef2 parsed it.")
    postings: list[Posting]
    cases: list[Case]


class CaseDetail(Case):
    invoice: InvoiceSummary
    questions: list[Question]


class PrecedentMatch(View):
    score: float = Field(description="Similarity from 0 to 1. Similar is not enough: check 'applicable'.")
    applicable: bool = Field(description="False means the platform will reject reusing this precedent.")
    blockers: list[str]
    precedent: Posting
    invoice: InvoiceSummary


class IssuedInvoice(View):
    ksef_number: str


class OpenQuestion(View):
    """An unanswered client question, with the invoice facts the client agent reads out."""

    id: int
    case_id: int
    text: str
    vehicle_plate: str | None
    seller_name: str
    gross: Decimal
    ksef_number: str


class ClientStatus(View):
    """Onboarding progress. The KSeF token itself is never included, only whether it is stored."""

    onboarded: bool
    company_name: str
    nip: str
    ksef_token_configured: bool
    ksef_token_last_four: str | None = None
    invoices_by_status: dict[str, int]
    open_questions: int


class KsefConfigured(View):
    configured: bool = True
    last_four: str


class StoredDocument(View):
    """A stored document. The text stays in the entity and is not part of this view."""

    id: int
    name: str
