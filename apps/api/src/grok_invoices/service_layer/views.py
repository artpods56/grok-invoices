"""What services return. Fields are read straight from the domain models' attributes."""

from datetime import date, datetime
from decimal import Decimal

from ksef2.fa3 import KsefInvoice
from pydantic import BaseModel, ConfigDict, Field

from grok_invoices.domain.models import Case, InvoiceStatus, Posting, Question


class View(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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
