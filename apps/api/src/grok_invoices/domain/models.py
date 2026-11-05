"""Supplementary models: what the platform knows beyond the KSeF invoice itself.

The invoice is ksef2's `KsefInvoice`. Don't re-model its fields here; read them from
`Invoice.document`. Models persist as their JSON, so a new field needs no migration
unless it's required (see STORE_VERSION in service_layer/unit_of_work.py).
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import cached_property
from typing import Any, Literal

from ksef2 import KSeFException
from ksef2.fa3 import KsefInvoice, parse_invoice_xml
from pydantic import BaseModel, ConfigDict, Field

from grok_invoices.domain.errors import Conflict, Invalid

Actor = Literal["invoice_agent", "regulations_agent", "client_agent", "accountant", "client", "ksef", "system"]
PostingSource = Literal["rule", "precedent", "regulation", "accountant"]
InvoiceStatus = Literal["received", "escalated", "posted"]
CaseStatus = Literal["open", "waiting_for_client", "resolved"]
QuestionStatus = Literal["open", "answered"]
VehicleUsage = Literal["company", "mixed", "private"]
EventType = Literal[
    "demo_reset", "invoice_received", "invoice_posted", "precedent_created", "posting_corrected",
    "case_opened", "case_taken_over", "question_asked", "question_answered",
    "client_fact_added", "vehicle_saved",
    "onboarding_started", "ksef_token_configured", "document_submitted",
]

VEHICLE_PLATE_KEY = "NrRej"
"""Where a fuel invoice names its vehicle: `body.additional_description`. KSeF metadata doesn't carry it."""

_CENT = Decimal("0.01")


def normalize_plate(plate: str) -> str:
    return re.sub(r"\s+", "", plate).upper()


class Entity(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: int = 0  # Assigned by the repository on add.


@dataclass(frozen=True)
class ReceivedDocument:
    """An invoice as KSeF delivers it. The KSeF number isn't part of the XML."""

    ksef_number: str
    xml: bytes


class Invoice(Entity):
    ksef_number: str
    source_xml: str = Field(repr=False)
    status: InvoiceStatus = "received"
    received_at: datetime

    @classmethod
    def receive(cls, document: ReceivedDocument, now: datetime) -> "Invoice":
        invoice = cls(ksef_number=document.ksef_number, source_xml=document.xml.decode(), received_at=now)
        try:
            _ = invoice.document
        except KSeFException as error:
            raise Invalid(f"Invoice {document.ksef_number} is not valid FA(3): {error}") from error
        return invoice

    @cached_property
    def document(self) -> KsefInvoice:
        return parse_invoice_xml(self.source_xml)

    @property
    def invoice_number(self) -> str:
        return self.document.body.invoice_number

    @property
    def seller_name(self) -> str:
        return self.document.seller.name

    @property
    def seller_nip(self) -> str:
        return self.document.seller.tax_id

    @property
    def issue_date(self) -> date:
        return self.document.body.issue_date

    @property
    def description(self) -> str:
        return "; ".join(row.name for row in self.document.body.rows if row.name)

    @property
    def vehicle_plate(self) -> str | None:
        """The plate as printed on the invoice, so an agent can read it aloud."""
        for entry in self.document.body.additional_description:
            if entry.key == VEHICLE_PLATE_KEY:
                return entry.value
        return None

    @property
    def net(self) -> Decimal:
        return sum((row.net_amount or Decimal(0) for row in self.document.body.rows), Decimal(0))

    @property
    def vat(self) -> Decimal:
        return sum((row.vat_amount or Decimal(0) for row in self.document.body.rows), Decimal(0))

    @property
    def gross(self) -> Decimal:
        return self.net + self.vat

    def deductible_vat(self, percent: int) -> Decimal:
        return (self.vat * percent / 100).quantize(_CENT, rounding=ROUND_HALF_UP)

    def escalate(self) -> None:
        if self.status != "received":
            raise Conflict(f"Only a received invoice can be escalated, this one is '{self.status}'")
        self.status = "escalated"

    def ensure_not_posted(self) -> None:
        if self.status == "posted":
            raise Conflict("Invoice is already posted. An accountant can correct the posting.")

    def mark_posted(self) -> None:
        self.ensure_not_posted()
        self.status = "posted"


class PrecedentConditions(BaseModel):
    """When a saved decision may be reused. Empty means it depends on nothing about a vehicle."""

    model_config = ConfigDict(extra="forbid")

    vehicle_usage: VehicleUsage | None = None
    vehicle_plate: str | None = None


class Posting(Entity):
    """A decision to book an invoice. Reusable postings are the precedents."""

    invoice_id: int
    case_id: int | None = None
    account: str
    vat_deduction_percent: int = Field(ge=0, le=100)
    deductible_vat: Decimal
    rationale: str
    confidence: float = Field(ge=0, le=1)
    actor: Actor
    source: PostingSource
    precedent_id: int | None = None
    legal_basis: str | None = None
    reusable: bool = False
    conditions: PrecedentConditions = Field(default_factory=PrecedentConditions)
    status: Literal["active", "superseded"] = "active"
    superseded_by: int | None = None
    created_at: datetime

    @property
    def is_active_precedent(self) -> bool:
        return self.reusable and self.status == "active"

    def supersede(self, replacement_id: int) -> None:
        if self.status != "active":
            raise Conflict("Only the active posting can be corrected")
        self.status = "superseded"
        self.superseded_by = replacement_id


class Case(Entity):
    """An invoice the invoice agent handed over because it can't be decided by rule or precedent."""

    invoice_id: int
    status: CaseStatus = "open"
    reason: str
    opened_by: Actor
    assignee: Actor | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status != "resolved"

    def ensure_open(self) -> None:
        if not self.is_open:
            raise Conflict("This case is already resolved")

    def ensure_can_decide(self, actor: Actor, source: PostingSource) -> None:
        if self.assignee == "accountant" and actor != "accountant":
            raise Conflict("The accountant has taken over this case")
        if source not in ("regulation", "accountant"):
            raise Conflict("This invoice is escalated and needs a regulation or accountant decision")
        if self.status == "waiting_for_client" and actor != "accountant":
            raise Conflict("This case is waiting for the client's answer")

    def wait_for_client(self) -> None:
        self.ensure_open()
        self.status = "waiting_for_client"

    def resume(self) -> None:
        self.ensure_open()
        self.status = "open"

    def take_over(self) -> None:
        self.ensure_open()
        self.assignee = "accountant"

    def resolve(self, now: datetime) -> None:
        self.status = "resolved"
        self.resolved_at = now


class Question(Entity):
    case_id: int
    text: str
    asked_by: Actor
    status: QuestionStatus = "open"
    answer: str | None = None
    answered_by: Actor | None = None
    created_at: datetime
    answered_at: datetime | None = None

    def record_answer(self, answer: str, actor: Actor, now: datetime) -> None:
        if self.status != "open":
            raise Conflict("This question is already answered")
        self.status = "answered"
        self.answer = answer
        self.answered_by = actor
        self.answered_at = now


class Vehicle(BaseModel):
    plate: str
    model: str
    usage: VehicleUsage


class Fact(BaseModel):
    key: str
    value: str
    source: Actor
    created_at: datetime


class Account(BaseModel):
    code: str
    name: str


class Client(Entity):
    """The accounting office's client, with what the agents may rely on about the business."""

    name: str
    nip: str
    phone: str | None = None
    ksef_since: datetime  # Invoices stored in KSeF before this aren't fetched.
    onboarded_at: datetime | None = None  # Set when the client agent registers the company.
    fleet: list[Vehicle] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    accounts: list[Account] = Field(default_factory=list)

    def vehicle(self, plate: str) -> Vehicle | None:
        wanted = normalize_plate(plate)
        return next((v for v in self.fleet if normalize_plate(v.plate) == wanted), None)

    def save_vehicle(self, vehicle: Vehicle) -> None:
        wanted = normalize_plate(vehicle.plate)
        self.fleet = [v for v in self.fleet if normalize_plate(v.plate) != wanted] + [vehicle]

    def add_fact(self, fact: Fact) -> None:
        self.facts = [*self.facts, fact]

    def require_account(self, code: str) -> None:
        if not any(account.code == code for account in self.accounts):
            raise Invalid(f"Account {code} is not in the chart of accounts")


class KsefToken(Entity):
    """The client's KSeF token, encrypted. No view or route returns this entity."""

    ciphertext: str
    last_four: str
    configured_at: datetime


class ClientDocument(Entity):
    """A document the client gave the agent. No route returns its content."""

    name: str
    content_text: str
    created_at: datetime


class Event(Entity):
    """The timeline. Agents can also follow it by id to know when there's work to do."""

    at: datetime
    actor: Actor
    type: EventType
    summary: str
    invoice_id: int | None = None
    case_id: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
