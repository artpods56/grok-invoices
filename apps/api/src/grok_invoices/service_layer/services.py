"""The platform's use cases. Every entrypoint goes through here, so the rules hold for all of them.

Each function owns its transaction and adds a timeline event for each change it makes.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal

from grok_invoices import ksef, seed
from grok_invoices.domain import rules
from grok_invoices.domain.errors import Conflict
from grok_invoices.domain.models import (
    Account, Actor, Case, Event, EventType, Fact, Invoice, Posting, Question, QuestionStatus, ReceivedDocument,
    Vehicle,
)
from grok_invoices.service_layer.commands import (
    AddFact, AnswerQuestion, AskClient, CorrectPosting, Escalate, PostInvoice, SaveVehicle,
)
from grok_invoices.service_layer.unit_of_work import UnitOfWork, init_store
from grok_invoices.service_layer.views import (
    CaseDetail, ClientProfile, InvoiceDetail, InvoiceSummary, IssuedInvoice, PrecedentMatch,
)

KsefSource = Literal["fixtures", "test"]


def _now() -> datetime:
    return datetime.now(UTC)


def _log(
    uow: UnitOfWork, actor: Actor, type_: EventType, summary: str,
    invoice_id: int | None = None, case_id: int | None = None, **data: object,
) -> None:
    uow.events.add(Event(
        at=_now(), actor=actor, type=type_, summary=summary, invoice_id=invoice_id, case_id=case_id, data=data,
    ))


def _on_hold(uow: UnitOfWork, invoice: Invoice) -> set[str]:
    open_cases = [case for case in uow.cases.all() if case.is_open]
    return rules.plates_on_hold((uow.invoices.require(case.invoice_id) for case in open_cases), excluding=invoice)


def _case_detail(uow: UnitOfWork, case: Case) -> CaseDetail:
    return CaseDetail(
        **case.model_dump(),
        invoice=InvoiceSummary.model_validate(uow.invoices.require(case.invoice_id)),
        questions=[q for q in uow.questions.all() if q.case_id == case.id],
    )


# --- Setup ---

def start_platform() -> None:
    init_store()
    with UnitOfWork() as uow:
        if uow.clients.get(1) is None:
            seed.populate(uow, _now())


def reset_demo() -> None:
    with UnitOfWork() as uow:
        uow.clear_for_reset()
        seed.populate(uow, _now())


# --- Client context ---

def get_client() -> ClientProfile:
    with UnitOfWork(write=False) as uow:
        return ClientProfile.model_validate(uow.client)


def list_accounts() -> list[Account]:
    return get_client().accounts


def add_fact(command: AddFact) -> ClientProfile:
    with UnitOfWork() as uow:
        client = uow.client
        client.add_fact(Fact(key=command.key, value=command.value, source=command.source, created_at=_now()))
        _log(uow, command.source, "client_fact_added", f"Nowy fakt o firmie: {command.key} = {command.value}", key=command.key)
        return ClientProfile.model_validate(client)


def save_vehicle(command: SaveVehicle) -> ClientProfile:
    with UnitOfWork() as uow:
        client = uow.client
        client.save_vehicle(Vehicle(plate=command.plate, model=command.model, usage=command.usage))
        _log(
            uow, command.actor, "vehicle_saved", f"Flota: {command.plate} ({command.model}, użytek: {command.usage})",
            plate=command.plate,
        )
        return ClientProfile.model_validate(client)


# --- Invoices ---

def ingest_documents(documents: Iterable[ReceivedDocument]) -> list[InvoiceSummary]:
    """Store invoices that arrived. One already stored is skipped, so syncing twice is safe."""
    with UnitOfWork() as uow:
        known = {invoice.ksef_number for invoice in uow.invoices.all()}
        added = []
        for document in documents:
            if document.ksef_number in known:
                continue
            invoice = uow.invoices.add(Invoice.receive(document, _now()))
            known.add(invoice.ksef_number)
            _log(
                uow, "ksef", "invoice_received",
                f"Nowa faktura {invoice.invoice_number}: {invoice.seller_name}, {invoice.gross} PLN", invoice.id,
                ksef_number=invoice.ksef_number,
            )
            added.append(InvoiceSummary.model_validate(invoice))
        return added


def sync_ksef(source: KsefSource = "fixtures") -> list[InvoiceSummary]:
    """Fetch new purchase invoices from KSeF TEST or the fixtures."""
    if source == "fixtures":
        return ingest_documents(seed.fixture_inbox())
    with UnitOfWork(write=False) as uow:
        client = uow.client
        known = {invoice.ksef_number for invoice in uow.invoices.all()}
    return ingest_documents(ksef.fetch_new(client.nip, client.ksef_since, known))


def issue_demo_invoice() -> IssuedInvoice:
    """Issue the stage demo's fuel invoice on KSeF TEST. It reaches the platform on the next sync."""
    client = get_client()
    now = _now()
    number = f"ON/{now:%Y/%m/%H%M%S}"
    return IssuedInvoice(ksef_number=ksef.issue_fuel_invoice(
        buyer_nip=client.nip, buyer_name=client.name, plate=seed.UNKNOWN_CAR, number=number, issued=now.date(),
    ))


def list_invoices(status: str | None = None) -> list[InvoiceSummary]:
    with UnitOfWork(write=False) as uow:
        return [InvoiceSummary.model_validate(i) for i in uow.invoices.all() if status is None or i.status == status]


def get_invoice(invoice_id: int) -> InvoiceDetail:
    with UnitOfWork(write=False) as uow:
        invoice = uow.invoices.require(invoice_id)
        return InvoiceDetail(
            **InvoiceSummary.model_validate(invoice).model_dump(),
            document=invoice.document,
            postings=[p for p in uow.postings.all() if p.invoice_id == invoice_id],
            cases=[c for c in uow.cases.all() if c.invoice_id == invoice_id],
        )


def get_invoice_xml(invoice_id: int) -> str:
    with UnitOfWork(write=False) as uow:
        return uow.invoices.require(invoice_id).source_xml


def search_precedents(invoice_id: int) -> list[PrecedentMatch]:
    """Past decisions similar to this invoice, best match first."""
    with UnitOfWork(write=False) as uow:
        invoice = uow.invoices.require(invoice_id)
        client = uow.client
        on_hold = _on_hold(uow, invoice)
        matches = []
        for posting in uow.postings.all():
            if not posting.is_active_precedent or posting.invoice_id == invoice_id:
                continue
            other = uow.invoices.require(posting.invoice_id)
            score = rules.similarity(invoice, other)
            if score == 0:
                continue
            blockers = rules.precedent_blockers(invoice, posting.conditions, client, on_hold)
            matches.append(PrecedentMatch(
                score=score, applicable=not blockers, blockers=blockers, precedent=posting,
                invoice=InvoiceSummary.model_validate(other),
            ))
        return sorted(matches, key=lambda match: match.score, reverse=True)


def post_invoice(invoice_id: int, command: PostInvoice) -> Posting:
    with UnitOfWork() as uow:
        invoice = uow.invoices.require(invoice_id)
        client = uow.client
        case = next((c for c in uow.cases.all() if c.invoice_id == invoice_id and c.is_open), None)

        invoice.ensure_not_posted()
        rules.ensure_posting_allowed(
            invoice, command.actor, command.source, case is not None, command.precedent_id, command.legal_basis,
        )
        client.require_account(command.account)
        if case is not None:
            case.ensure_can_decide(command.actor, command.source)

        if command.source == "precedent":
            precedent = uow.postings.require(command.precedent_id)
            if not precedent.is_active_precedent:
                raise Conflict(f"Posting {command.precedent_id} is not an active precedent")
            blockers = rules.precedent_blockers(invoice, precedent.conditions, client, _on_hold(uow, invoice))
            if blockers:
                raise Conflict(f"Precedent does not apply: {'; '.join(blockers)}")

        posting = uow.postings.add(Posting(
            invoice_id=invoice_id,
            case_id=case.id if case else None,
            deductible_vat=invoice.deductible_vat(command.vat_deduction_percent),
            created_at=_now(),
            **command.model_dump(exclude={"conditions"}),
            conditions=command.conditions,
        ))
        invoice.mark_posted()
        if case is not None:
            case.resolve(_now())

        how = {
            "rule": "dekretacja bezpośrednia",
            "precedent": f"zastosowano precedens #{command.precedent_id}",
            "regulation": "decyzja na podstawie przepisów",
            "accountant": "decyzja księgowej",
        }[command.source]
        _log(
            uow, command.actor, "invoice_posted",
            f"Faktura {invoice.invoice_number} → konto {command.account}, VAT {command.vat_deduction_percent}% ({how})",
            invoice_id, posting.case_id,
            posting_id=posting.id, source=command.source, confidence=command.confidence, rationale=command.rationale,
            precedent_id=command.precedent_id, legal_basis=command.legal_basis,
        )
        if command.reusable:
            _log(
                uow, command.actor, "precedent_created", f"Nowy precedens #{posting.id}: {command.rationale}",
                invoice_id, posting.case_id, posting_id=posting.id,
            )
        return posting


def correct_posting(posting_id: int, command: CorrectPosting) -> Posting:
    """An accountant's override, which also becomes the precedent in place of the old decision."""
    with UnitOfWork() as uow:
        old = uow.postings.require(posting_id)
        if old.status != "active":
            raise Conflict("Only the active posting can be corrected")
        uow.client.require_account(command.account)
        invoice = uow.invoices.require(old.invoice_id)
        new = uow.postings.add(Posting(
            invoice_id=old.invoice_id,
            case_id=old.case_id,
            account=command.account,
            vat_deduction_percent=command.vat_deduction_percent,
            deductible_vat=invoice.deductible_vat(command.vat_deduction_percent),
            rationale=command.rationale,
            confidence=1.0,
            actor="accountant",
            source="accountant",
            legal_basis=command.legal_basis,
            reusable=True,
            conditions=command.conditions if command.conditions is not None else old.conditions,
            created_at=_now(),
        ))
        old.supersede(new.id)
        citing = [p.id for p in uow.postings.all() if p.precedent_id == posting_id and p.status == "active"]
        _log(
            uow, "accountant", "posting_corrected",
            f"Księgowa poprawiła dekretację #{posting_id} → konto {command.account}, VAT {command.vat_deduction_percent}%",
            old.invoice_id, old.case_id,
            old_posting_id=posting_id, posting_id=new.id, rationale=command.rationale, postings_citing_old=citing,
        )
        return new


# --- Cases and client questions ---

def escalate_invoice(invoice_id: int, command: Escalate) -> CaseDetail:
    with UnitOfWork() as uow:
        invoice = uow.invoices.require(invoice_id)
        invoice.escalate()
        held = rules.hold_blockers(invoice, _on_hold(uow, invoice))
        if held:
            raise Conflict(f"Invoice is on hold: {held[0]}")
        case = uow.cases.add(Case(invoice_id=invoice_id, reason=command.reason, opened_by=command.actor, created_at=_now()))
        _log(uow, command.actor, "case_opened", f"Eskalacja faktury {invoice.invoice_number}: {command.reason}", invoice_id, case.id)
        return _case_detail(uow, case)


def list_cases(status: str | None = None) -> list[Case]:
    with UnitOfWork(write=False) as uow:
        return [c for c in uow.cases.all() if status is None or c.status == status]


def get_case(case_id: int) -> CaseDetail:
    with UnitOfWork(write=False) as uow:
        return _case_detail(uow, uow.cases.require(case_id))


def ask_client(case_id: int, command: AskClient) -> Question:
    with UnitOfWork() as uow:
        case = uow.cases.require(case_id)
        case.wait_for_client()
        question = uow.questions.add(Question(case_id=case_id, text=command.text, asked_by=command.actor, created_at=_now()))
        _log(uow, command.actor, "question_asked", f"Pytanie do klienta: {command.text}", case.invoice_id, case_id, question_id=question.id)
        return question


def list_questions(status: QuestionStatus | None = None) -> list[Question]:
    with UnitOfWork(write=False) as uow:
        return [q for q in uow.questions.all() if status is None or q.status == status]


def answer_question(question_id: int, command: AnswerQuestion) -> Question:
    with UnitOfWork() as uow:
        question = uow.questions.require(question_id)
        case = uow.cases.require(question.case_id)
        case.ensure_open()
        question.record_answer(command.answer, command.actor, _now())
        if not any(q.status == "open" for q in uow.questions.all() if q.case_id == case.id):
            case.resume()
        _log(uow, command.actor, "question_answered", f"Odpowiedź klienta: {command.answer}", case.invoice_id, case.id, question_id=question_id)
        return question


def take_over_case(case_id: int) -> CaseDetail:
    with UnitOfWork() as uow:
        case = uow.cases.require(case_id)
        case.take_over()
        _log(uow, "accountant", "case_taken_over", f"Księgowa przejęła sprawę #{case_id}", case.invoice_id, case_id)
        return _case_detail(uow, case)


# --- Timeline ---

def list_events(after: int = 0, limit: int = 200) -> list[Event]:
    """Oldest first. Pass the last seen id as `after` to read only what's new."""
    with UnitOfWork(write=False) as uow:
        return uow.events.after(after, limit)
