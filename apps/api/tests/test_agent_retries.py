"""Role-independent business protections for agent retries and precedent reuse."""

import pytest

from grok_invoices.domain.errors import Conflict
from grok_invoices.seed import COMPANY_VAN, UNKNOWN_CAR
from grok_invoices.service_layer import commands, services


def test_identical_questions_and_answers_do_not_duplicate_events_or_postings(api):
    invoices = services.sync_ksef("fixtures")
    invoice = next(item for item in invoices if item.vehicle_plate == UNKNOWN_CAR)
    case = services.escalate_invoice(invoice.id, commands.Escalate(reason="Unknown vehicle"))
    ask = commands.AskClient(text="Which vehicle and business purpose?")
    question = services.ask_client(case.id, ask)
    before = len(services.list_events())
    assert services.ask_client(case.id, ask).id == question.id
    assert len(services.list_events()) == before

    answer = commands.AnswerQuestion(answer="Skoda, mixed use, business travel")
    services.answer_question(question.id, answer)
    before = len(services.list_events())
    assert services.answer_question(question.id, answer).answer == answer.answer
    assert len(services.list_events()) == before
    assert services.get_invoice(invoice.id).postings == []
    # An answer resumes analysis; it never certifies tax treatment or books the invoice.
    assert services.get_case(case.id).status == "open"
    services.post_invoice(invoice.id, commands.PostInvoice(
        account="403", vat_deduction_percent=50, rationale="SYNTHETIC DEMO",
        confidence=0.9, actor="regulations_agent", source="regulation", legal_basis="SYNTHETIC DEMO",
    ))
    before = len(services.list_events())
    assert services.answer_question(question.id, answer).answer == answer.answer
    assert len(services.list_events()) == before
    assert len(services.get_invoice(invoice.id).postings) == 1
    with pytest.raises(Conflict):
        services.answer_question(question.id, commands.AnswerQuestion(answer="A different answer"))


@pytest.mark.parametrize(("account", "percent"), [("402", 50), ("403", 100)])
def test_a_rest_caller_cannot_change_the_reused_precedent_outcome(api, account, percent):
    fuel = next(item for item in services.sync_ksef("fixtures") if item.vehicle_plate == COMPANY_VAN)
    precedent = services.search_precedents(fuel.id)[0].precedent
    before = len(services.list_events())
    response = api.post(f"/api/invoices/{fuel.id}/postings", json={
        "account": account, "vat_deduction_percent": percent, "rationale": "Reuse",
        "confidence": 0.9, "actor": "invoice_agent", "source": "precedent", "precedent_id": precedent.id,
    })
    assert response.status_code == 409
    assert "preserve" in response.json()["detail"]
    assert len(services.list_events()) == before
    assert services.get_invoice(fuel.id).status == "received"
