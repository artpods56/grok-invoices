from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Actor = Literal["invoice_agent", "regulations_agent", "client_agent", "accountant", "client", "ksef", "system"]
PostingSource = Literal["rule", "precedent", "regulation", "accountant"]
InvoiceStatus = Literal["received", "escalated", "posted"]
CaseStatus = Literal["open", "waiting_for_client", "resolved"]
QuestionStatus = Literal["open", "answered"]
VehicleUsage = Literal["company", "mixed", "private"]


class InvoiceIn(BaseModel):
    ksef_number: str = Field(min_length=1)
    seller_name: str = Field(min_length=1)
    seller_nip: str = Field(min_length=1)
    description: str = Field(min_length=1)
    vehicle_plate: str | None = None
    net: Decimal = Field(ge=0, decimal_places=2)
    vat: Decimal = Field(ge=0, decimal_places=2)
    gross: Decimal = Field(ge=0, decimal_places=2)
    issue_date: str

    @model_validator(mode="after")
    def amounts_add_up(self) -> Self:
        if self.net + self.vat != self.gross:
            raise ValueError("net + vat must equal gross")
        return self


class PostingIn(BaseModel):
    account: str
    vat_deduction_percent: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    actor: Actor
    source: PostingSource
    precedent_id: int | None = Field(default=None, description="Required when source is 'precedent'.")
    legal_basis: str | None = Field(default=None, description="Required when source is 'regulation'.")
    reusable: bool = Field(default=False, description="Save this decision as a precedent for future invoices.")
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="When a reusable decision applies. Supported: {'vehicle_usage': 'mixed'}.",
    )


class CorrectionIn(BaseModel):
    account: str
    vat_deduction_percent: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)
    legal_basis: str | None = None
    reusable: bool = False
    conditions: dict[str, Any] = Field(default_factory=dict)


class EscalationIn(BaseModel):
    reason: str = Field(min_length=1)
    actor: Actor = "invoice_agent"


class QuestionIn(BaseModel):
    text: str = Field(min_length=1)
    actor: Actor = "regulations_agent"


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1)
    actor: Actor = "client_agent"


class FactIn(BaseModel):
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source: Actor = "client_agent"


class Vehicle(BaseModel):
    plate: str
    model: str
    usage: VehicleUsage


class VehicleIn(Vehicle):
    actor: Actor = "regulations_agent"


class Fact(BaseModel):
    id: int
    key: str
    value: str
    source: str
    created_at: str


class Client(BaseModel):
    name: str
    nip: str
    fleet: list[Vehicle]
    facts: list[Fact]


class Account(BaseModel):
    code: str
    name: str


class Invoice(BaseModel):
    id: int
    ksef_number: str
    seller_name: str
    seller_nip: str
    description: str
    vehicle_plate: str | None
    net: Decimal
    vat: Decimal
    gross: Decimal
    issue_date: str
    status: InvoiceStatus
    received_at: str


class Posting(BaseModel):
    id: int
    invoice_id: int
    case_id: int | None
    account: str
    vat_deduction_percent: int
    deductible_vat: Decimal
    rationale: str
    confidence: float
    actor: str
    source: PostingSource
    precedent_id: int | None
    legal_basis: str | None
    reusable: bool
    conditions: dict[str, Any]
    status: Literal["active", "superseded"]
    superseded_by: int | None
    created_at: str


class Question(BaseModel):
    id: int
    case_id: int
    text: str
    asked_by: str
    status: QuestionStatus
    answer: str | None
    answered_by: str | None
    created_at: str
    answered_at: str | None


class Case(BaseModel):
    id: int
    invoice_id: int
    status: CaseStatus
    reason: str
    opened_by: str
    assignee: str | None
    created_at: str
    resolved_at: str | None


class CaseDetail(Case):
    invoice: Invoice
    questions: list[Question]


class InvoiceDetail(Invoice):
    postings: list[Posting]
    cases: list[Case]


class PrecedentMatch(BaseModel):
    score: float = Field(description="Similarity from 0 to 1. Similar is not enough: check 'applicable'.")
    applicable: bool = Field(description="False means the platform will reject reusing this precedent.")
    blockers: list[str]
    precedent: Posting
    invoice: Invoice


class Event(BaseModel):
    id: int
    at: str
    actor: str
    type: str
    summary: str
    invoice_id: int | None
    case_id: int | None
    data: dict[str, Any]


AgentMode = Literal["demo", "xai"]


class AgentRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: AgentMode = "demo"
    invoice_id: int | None = Field(default=None, gt=0)
    limit: int = Field(default=20, ge=1, le=50)


class AgentProposal(BaseModel):
    """A model can propose a category or stop. It cannot choose amounts or accounts."""
    model_config = ConfigDict(extra="forbid")
    category: Literal["it_services", "vehicle_fuel", "unsupported"]
    action: Literal["analyse", "block"]
    rationale: str = Field(min_length=1, max_length=2000)


class ContextAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    vehicle_plate: str | None = Field(default=None, max_length=20)
    usage: VehicleUsage | None = None
    business_purpose: str | None = Field(default=None, max_length=1000)
    vehicle_model: str | None = Field(default=None, max_length=100)
