"""What callers can ask the platform to do. HTTP, MCP and the agents all use these."""

from pydantic import BaseModel, ConfigDict, Field

from grok_invoices.domain.models import Actor, PostingSource, PrecedentConditions, VehicleUsage


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PostInvoice(Command):
    account: str
    vat_deduction_percent: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    actor: Actor
    source: PostingSource
    precedent_id: int | None = Field(default=None, description="Required when source is 'precedent'.")
    legal_basis: str | None = Field(default=None, description="Required when source is 'regulation'.")
    reusable: bool = Field(default=False, description="Save this decision as a precedent for future invoices.")
    conditions: PrecedentConditions = Field(default_factory=PrecedentConditions)


class CorrectPosting(Command):
    """An accountant's override. It always becomes a precedent, and keeps the old conditions unless new ones are given."""

    account: str
    vat_deduction_percent: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)
    legal_basis: str | None = None
    conditions: PrecedentConditions | None = None


class Escalate(Command):
    reason: str = Field(min_length=1)
    actor: Actor = "invoice_agent"


class AskClient(Command):
    text: str = Field(min_length=1)
    actor: Actor = "regulations_agent"


class AnswerQuestion(Command):
    answer: str = Field(min_length=1)
    actor: Actor = "client_agent"


class AddFact(Command):
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source: Actor = "client_agent"


class SaveVehicle(Command):
    plate: str = Field(min_length=1)
    model: str = Field(min_length=1)
    usage: VehicleUsage
    actor: Actor = "regulations_agent"
