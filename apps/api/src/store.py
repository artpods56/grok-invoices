"""Platform state and the rules agents can't bypass. Every write adds a timeline event."""

import json
import hashlib
import re
import sqlite3
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException

from apps.api.src.agent_policy import DEMO_POLICY
from apps.api.src.schemas import (
    AgentProposal, AnswerIn, ContextAnswerIn, CorrectionIn, EscalationIn, FactIn,
    InvoiceDetail, InvoiceIn, PostingIn, QuestionIn, VehicleIn,
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _not_found(what: str, id_: int) -> HTTPException:
    return HTTPException(404, f"{what} {id_} not found")


def normalize_plate(plate: str | None) -> str | None:
    return re.sub(r"\s+", "", plate).upper() if plate else None


def log_event(
    conn: sqlite3.Connection, actor: str, type_: str, summary: str,
    invoice_id: int | None = None, case_id: int | None = None, data: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "INSERT INTO events (at, actor, type, summary, invoice_id, case_id, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_now(), actor, type_, summary, invoice_id, case_id, json.dumps(data or {}, ensure_ascii=False)),
    )


# --- Reads ---

def _posting_dict(row: sqlite3.Row) -> dict[str, Any]:
    posting = dict(row)
    vat = Decimal(posting.pop("invoice_vat"))
    posting["deductible_vat"] = (vat * posting["vat_deduction_percent"] / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    posting["reusable"] = bool(posting["reusable"])
    posting["conditions"] = json.loads(posting["conditions"])
    return posting


_POSTING_SELECT = "SELECT p.*, i.vat AS invoice_vat FROM postings p JOIN invoices i ON i.id = p.invoice_id"


def get_client(conn: sqlite3.Connection) -> dict[str, Any]:
    client = conn.execute("SELECT name, nip FROM client").fetchone()
    return {
        **dict(client),
        "fleet": [dict(r) for r in conn.execute("SELECT plate, model, usage FROM vehicles ORDER BY plate")],
        "facts": [dict(r) for r in conn.execute("SELECT * FROM client_facts ORDER BY id")],
    }


def list_accounts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT code, name FROM accounts ORDER BY code")]


def list_invoices(conn: sqlite3.Connection, status: str | None) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute("SELECT * FROM invoices WHERE status = ? ORDER BY id", (status,))
    else:
        rows = conn.execute("SELECT * FROM invoices ORDER BY id")
    return [dict(r) for r in rows]


def _invoice_row(conn: sqlite3.Connection, invoice_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        raise _not_found("Invoice", invoice_id)
    return row


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> dict[str, Any]:
    invoice = dict(_invoice_row(conn, invoice_id))
    invoice["postings"] = [
        _posting_dict(r)
        for r in conn.execute(f"{_POSTING_SELECT} WHERE p.invoice_id = ? ORDER BY p.id", (invoice_id,))
    ]
    invoice["cases"] = [dict(r) for r in conn.execute("SELECT * FROM cases WHERE invoice_id = ? ORDER BY id", (invoice_id,))]
    return invoice


def _posting_row(conn: sqlite3.Connection, posting_id: int) -> sqlite3.Row:
    row = conn.execute(f"{_POSTING_SELECT} WHERE p.id = ?", (posting_id,)).fetchone()
    if row is None:
        raise _not_found("Posting", posting_id)
    return row


def list_cases(conn: sqlite3.Connection, status: str | None) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute("SELECT * FROM cases WHERE status = ? ORDER BY id", (status,))
    else:
        rows = conn.execute("SELECT * FROM cases ORDER BY id")
    return [dict(r) for r in rows]


def _case_row(conn: sqlite3.Connection, case_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise _not_found("Case", case_id)
    return row


def get_case(conn: sqlite3.Connection, case_id: int) -> dict[str, Any]:
    case = dict(_case_row(conn, case_id))
    case["invoice"] = dict(_invoice_row(conn, case["invoice_id"]))
    case["questions"] = [dict(r) for r in conn.execute("SELECT * FROM questions WHERE case_id = ? ORDER BY id", (case_id,))]
    return case


def list_questions(conn: sqlite3.Connection, status: str | None) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute("SELECT * FROM questions WHERE status = ? ORDER BY id", (status,))
    else:
        rows = conn.execute("SELECT * FROM questions ORDER BY id")
    return [dict(r) for r in rows]


def list_events(conn: sqlite3.Connection, after: int, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM events WHERE id > ? ORDER BY id LIMIT ?", (after, limit))
    return [{**dict(r), "data": json.loads(r["data"])} for r in rows]


# --- Precedents ---

def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) >= 3 and not t.isdigit()}


def _similarity(a: sqlite3.Row, b: sqlite3.Row) -> float:
    ta, tb = _tokens(a["description"]), _tokens(b["description"])
    overlap = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    same_seller = 1.0 if a["seller_nip"] == b["seller_nip"] else 0.0
    return round(0.5 * same_seller + 0.5 * overlap, 3)


def precedent_blockers(conn: sqlite3.Connection, invoice: sqlite3.Row, conditions: dict[str, Any]) -> list[str]:
    """Why a precedent can't be reused here, however similar the invoice looks."""
    supported = {"vehicle_usage", "vehicle_plate", "category", "policy_version", "chart_version", "valid_from", "valid_until"}
    blockers = []
    if any(not isinstance(value, str) for value in conditions.values()):
        return ["precedent conditions must contain supported string values"]
    if set(conditions) - supported:
        blockers.append("the precedent has unsupported conditions")
    if "vehicle_plate" in conditions and normalize_plate(conditions["vehicle_plate"]) != invoice["vehicle_plate"]:
        blockers.append(f"vehicle {invoice['vehicle_plate']} does not match the precedent's vehicle scope")
    if "category" in conditions and conditions["category"] != invoice_category(invoice["description"]):
        blockers.append("the expense category does not match")
    policy = agent_policy(conn)
    for key, policy_key in (("policy_version", "version"), ("chart_version", "chart_version")):
        if key in conditions and conditions[key] != (policy or {}).get(policy_key):
            blockers.append(f"the {key} has changed")
    try:
        issued = date.fromisoformat(invoice["issue_date"])
        if "valid_from" in conditions and issued < date.fromisoformat(conditions["valid_from"]):
            blockers.append("the invoice predates the precedent's application period")
        if "valid_until" in conditions and issued > date.fromisoformat(conditions["valid_until"]):
            blockers.append("the invoice is outside the precedent's application period")
    except (ValueError, TypeError):
        blockers.append("the application date cannot be verified")
    required_usage = conditions.get("vehicle_usage")
    if not required_usage:
        return blockers
    plate = invoice["vehicle_plate"]
    if not plate:
        return blockers + ["the invoice does not name a vehicle"]
    vehicle = conn.execute("SELECT usage FROM vehicles WHERE plate = ?", (plate,)).fetchone()
    if vehicle is None:
        return blockers + [f"vehicle {plate} is not on the client's fleet"]
    if vehicle["usage"] != required_usage:
        return blockers + [f"vehicle {plate} has usage '{vehicle['usage']}', the precedent requires '{required_usage}'"]
    return blockers


def search_precedents(conn: sqlite3.Connection, invoice_id: int) -> list[dict[str, Any]]:
    invoice = _invoice_row(conn, invoice_id)
    matches = []
    for row in conn.execute(
        f"{_POSTING_SELECT} WHERE p.reusable = 1 AND p.status = 'active' AND p.invoice_id != ?", (invoice_id,)
    ).fetchall():
        other = _invoice_row(conn, row["invoice_id"])
        score = _similarity(invoice, other)
        if score == 0:
            continue
        posting = _posting_dict(row)
        blockers = precedent_blockers(conn, invoice, posting["conditions"])
        matches.append({
            "score": score, "applicable": not blockers, "blockers": blockers,
            "precedent": posting, "invoice": dict(other),
        })
    return sorted(matches, key=lambda m: m["score"], reverse=True)


# --- Writes ---

def insert_invoice(conn: sqlite3.Connection, body: InvoiceIn) -> dict[str, Any]:
    if conn.execute("SELECT 1 FROM invoices WHERE ksef_number = ?", (body.ksef_number,)).fetchone():
        raise HTTPException(409, f"Invoice {body.ksef_number} already exists")
    cursor = conn.execute(
        "INSERT INTO invoices (ksef_number, seller_name, seller_nip, description, vehicle_plate, net, vat, gross,"
        " issue_date, status, received_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'received', ?)",
        (
            body.ksef_number, body.seller_name, body.seller_nip, body.description,
            normalize_plate(body.vehicle_plate), str(body.net), str(body.vat), str(body.gross),
            body.issue_date, _now(),
        ),
    )
    invoice_id = cursor.lastrowid
    log_event(
        conn, "ksef", "invoice_received",
        f"Invoice received {body.ksef_number}: {body.seller_name}, {body.gross} PLN", invoice_id,
    )
    return dict(_invoice_row(conn, invoice_id))


def _require_account(conn: sqlite3.Connection, code: str) -> None:
    if not conn.execute("SELECT 1 FROM accounts WHERE code = ?", (code,)).fetchone():
        raise HTTPException(422, f"Account {code} is not in the chart of accounts")


def _insert_posting(
    conn: sqlite3.Connection, invoice_id: int, case_id: int | None, body: PostingIn | CorrectionIn,
    actor: str, source: str, confidence: float, precedent_id: int | None,
) -> int:
    return conn.execute(
        "INSERT INTO postings (invoice_id, case_id, account, vat_deduction_percent, rationale, confidence, actor,"
        " source, precedent_id, legal_basis, reusable, conditions, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)",
        (
            invoice_id, case_id, body.account, body.vat_deduction_percent, body.rationale, confidence, actor,
            source, precedent_id, body.legal_basis,
            int(body.reusable), json.dumps(body.conditions, ensure_ascii=False), _now(),
        ),
    ).lastrowid


def create_posting(conn: sqlite3.Connection, invoice_id: int, body: PostingIn) -> dict[str, Any]:
    invoice = _invoice_row(conn, invoice_id)
    if invoice["status"] == "posted":
        raise HTTPException(409, "Invoice is already posted. An accountant can correct the posting.")

    if body.source == "accountant" and body.actor != "accountant":
        raise HTTPException(422, "Only the accountant can use source 'accountant'")
    if body.source == "regulation" and not body.legal_basis:
        raise HTTPException(422, "A regulation decision needs a legal_basis")
    if body.source == "precedent" and body.precedent_id is None:
        raise HTTPException(422, "A precedent posting needs a precedent_id")
    if body.source != "precedent" and body.precedent_id is not None:
        raise HTTPException(422, "precedent_id is only valid with source 'precedent'")
    _require_account(conn, body.account)

    case = conn.execute(
        "SELECT * FROM cases WHERE invoice_id = ? AND status != 'resolved'", (invoice_id,)
    ).fetchone()
    if case is not None:
        if case["assignee"] == "accountant" and body.actor != "accountant":
            raise HTTPException(409, "The accountant has taken over this case")
        if body.source not in ("regulation", "accountant"):
            raise HTTPException(409, "This invoice is escalated and needs a regulation or accountant decision")
        if case["status"] == "waiting_for_client" and body.actor != "accountant":
            raise HTTPException(409, "This case is waiting for the client's answer")

    if body.source == "precedent":
        precedent = _posting_row(conn, body.precedent_id)
        if not precedent["reusable"] or precedent["status"] != "active":
            raise HTTPException(409, f"Posting {body.precedent_id} is not an active precedent")
        if body.account != precedent["account"] or body.vat_deduction_percent != precedent["vat_deduction_percent"]:
            raise HTTPException(409, "A reused precedent must retain its account and VAT treatment")
        blockers = precedent_blockers(conn, invoice, json.loads(precedent["conditions"]))
        if blockers:
            raise HTTPException(409, f"Precedent does not apply: {'; '.join(blockers)}")

    case_id = case["id"] if case is not None else None
    posting_id = _insert_posting(conn, invoice_id, case_id, body, body.actor, body.source, body.confidence, body.precedent_id)
    conn.execute("UPDATE invoices SET status = 'posted' WHERE id = ?", (invoice_id,))
    if case is not None:
        conn.execute("UPDATE cases SET status = 'resolved', resolved_at = ? WHERE id = ?", (_now(), case_id))

    how = {
        "rule": "direct rule posting",
        "precedent": f"precedent #{body.precedent_id} applied",
        "regulation": "regulatory decision",
        "accountant": "accountant decision",
    }[body.source]
    log_event(
        conn, body.actor, "invoice_posted",
        f"Invoice {invoice['ksef_number']} -> account {body.account}, VAT deduction {body.vat_deduction_percent}% ({how})",
        invoice_id, case_id,
        {
            "posting_id": posting_id, "source": body.source, "confidence": body.confidence,
            "rationale": body.rationale, "precedent_id": body.precedent_id, "legal_basis": body.legal_basis,
        },
    )
    if body.reusable:
        log_event(
            conn, body.actor, "precedent_created", f"Precedent created #{posting_id}: {body.rationale}",
            invoice_id, case_id, {"posting_id": posting_id, "conditions": body.conditions},
        )
    return _posting_dict(_posting_row(conn, posting_id))


def correct_posting(conn: sqlite3.Connection, posting_id: int, body: CorrectionIn) -> dict[str, Any]:
    old = _posting_row(conn, posting_id)
    if old["status"] != "active":
        raise HTTPException(409, "Only the active posting can be corrected")
    _require_account(conn, body.account)
    new_id = _insert_posting(conn, old["invoice_id"], old["case_id"], body, "accountant", "accountant", 1.0, None)
    conn.execute("UPDATE postings SET status = 'superseded', superseded_by = ? WHERE id = ?", (new_id, posting_id))
    cited_by = [r["id"] for r in conn.execute("SELECT id FROM postings WHERE precedent_id = ? AND status = 'active'", (posting_id,))]
    log_event(
        conn, "accountant", "posting_corrected",
        f"Accountant corrected posting #{posting_id} -> account {body.account}, VAT deduction {body.vat_deduction_percent}%",
        old["invoice_id"], old["case_id"],
        {"old_posting_id": posting_id, "posting_id": new_id, "rationale": body.rationale, "postings_citing_old": cited_by},
    )
    return _posting_dict(_posting_row(conn, new_id))


def escalate_invoice(conn: sqlite3.Connection, invoice_id: int, body: EscalationIn) -> dict[str, Any]:
    invoice = _invoice_row(conn, invoice_id)
    if invoice["status"] != "received":
        raise HTTPException(409, f"Only a received invoice can be escalated, this one is '{invoice['status']}'")
    case_id = conn.execute(
        "INSERT INTO cases (invoice_id, status, reason, opened_by, created_at) VALUES (?, 'open', ?, ?, ?)",
        (invoice_id, body.reason, body.actor, _now()),
    ).lastrowid
    conn.execute("UPDATE invoices SET status = 'escalated' WHERE id = ?", (invoice_id,))
    log_event(conn, body.actor, "case_opened", f"Invoice escalated {invoice['ksef_number']}: {body.reason}", invoice_id, case_id)
    return get_case(conn, case_id)


def _open_case_row(conn: sqlite3.Connection, case_id: int) -> sqlite3.Row:
    case = _case_row(conn, case_id)
    if case["status"] == "resolved":
        raise HTTPException(409, "This case is already resolved")
    return case


def ask_question(conn: sqlite3.Connection, case_id: int, body: QuestionIn) -> dict[str, Any]:
    case = _open_case_row(conn, case_id)
    question_id = conn.execute(
        "INSERT INTO questions (case_id, text, asked_by, status, created_at) VALUES (?, ?, ?, 'open', ?)",
        (case_id, body.text, body.actor, _now()),
    ).lastrowid
    conn.execute("UPDATE cases SET status = 'waiting_for_client' WHERE id = ?", (case_id,))
    log_event(conn, body.actor, "question_asked", f"Client question: {body.text}", case["invoice_id"], case_id, {"question_id": question_id})
    return dict(conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone())


def answer_question(conn: sqlite3.Connection, question_id: int, body: AnswerIn) -> dict[str, Any]:
    question = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    if question is None:
        raise _not_found("Question", question_id)
    if question["status"] != "open":
        raise HTTPException(409, "This question is already answered")
    case = _open_case_row(conn, question["case_id"])
    conn.execute(
        "UPDATE questions SET status = 'answered', answer = ?, answered_by = ?, answered_at = ? WHERE id = ?",
        (body.answer, body.actor, _now(), question_id),
    )
    still_open = conn.execute(
        "SELECT 1 FROM questions WHERE case_id = ? AND status = 'open'", (case["id"],)
    ).fetchone()
    if still_open is None:
        conn.execute("UPDATE cases SET status = 'open' WHERE id = ?", (case["id"],))
    log_event(conn, body.actor, "question_answered", f"Client answer: {body.answer}", case["invoice_id"], case["id"], {"question_id": question_id})
    return dict(conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone())


def take_over_case(conn: sqlite3.Connection, case_id: int) -> dict[str, Any]:
    case = _open_case_row(conn, case_id)
    conn.execute("UPDATE cases SET assignee = 'accountant' WHERE id = ?", (case_id,))
    log_event(conn, "accountant", "case_taken_over", f"Accountant took over case #{case_id}", case["invoice_id"], case_id)
    return get_case(conn, case_id)


def add_fact(conn: sqlite3.Connection, body: FactIn) -> dict[str, Any]:
    fact_id = conn.execute(
        "INSERT INTO client_facts (key, value, source, created_at) VALUES (?, ?, ?, ?)",
        (body.key, body.value, body.source, _now()),
    ).lastrowid
    log_event(conn, body.source, "client_fact_added", f"Company fact: {body.key} = {body.value}", data={"fact_id": fact_id})
    return get_client(conn)


def add_vehicle(conn: sqlite3.Connection, body: VehicleIn) -> dict[str, Any]:
    plate = normalize_plate(body.plate)
    conn.execute(
        "INSERT INTO vehicles (plate, model, usage) VALUES (?, ?, ?)"
        " ON CONFLICT (plate) DO UPDATE SET model = excluded.model, usage = excluded.usage",
        (plate, body.model, body.usage),
    )
    log_event(conn, body.actor, "vehicle_saved", f"Fleet: {plate} ({body.model}, usage: {body.usage})", data={"plate": plate})
    return get_client(conn)


# --- Agent workflow: the same database and transaction as the platform API ---

def invoice_category(description: str) -> str:
    if re.search(r"\b(fuel|diesel|petrol|paliwo|tankowanie)\b", description, re.I):
        return "vehicle_fuel"
    if re.search(r"\b(it|software|hosting)\b", description, re.I):
        return "it_services"
    return "unsupported"


def agent_policy(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT value FROM client_facts WHERE key = 'agent_policy' ORDER BY id DESC LIMIT 1").fetchone()
    try:
        value = json.loads(row[0]) if row else None
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def setup_demo_policy(conn: sqlite3.Connection) -> dict:
    if get_client(conn)["nip"] != "8943210098":
        raise HTTPException(409, "The synthetic policy is restricted to the seeded demo company")
    if agent_policy(conn) != DEMO_POLICY:
        add_fact(conn, FactIn(key="agent_policy", value=json.dumps(DEMO_POLICY), source="system"))
    return DEMO_POLICY


def agent_context(conn: sqlite3.Connection, invoice_id: int) -> dict:
    invoice = get_invoice(conn, invoice_id)
    return {
        "invoice": invoice, "client": get_client(conn), "accounts": list_accounts(conn),
        "policy": agent_policy(conn), "precedents": search_precedents(conn, invoice_id),
        "questions": [dict(q) for q in conn.execute(
            "SELECT q.* FROM questions q JOIN cases c ON c.id = q.case_id WHERE c.invoice_id = ? ORDER BY q.id",
            (invoice_id,),
        )],
    }


def context_fingerprint(context: dict) -> str:
    return hashlib.sha256(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()


def log_agent_analysis(conn: sqlite3.Connection, invoice_id: int, mode: str, triage: AgentProposal, final: AgentProposal) -> None:
    log_event(conn, "invoice_agent", "agent_analysis", "Invoice agent proposal validated by the platform", invoice_id,
              data={"mode": mode, "category": triage.category, "action": triage.action, "rationale": triage.rationale})
    if final is not triage:
        log_event(conn, "regulations_agent", "agent_analysis", "Regulatory agent proposal validated by the platform", invoice_id,
                  data={"mode": mode, "category": final.category, "action": final.action, "rationale": final.rationale})


def agent_result(conn: sqlite3.Connection, invoice_id: int) -> dict:
    invoice = get_invoice(conn, invoice_id)
    event = conn.execute(
        "SELECT data FROM events WHERE invoice_id = ? AND type = 'agent_state' ORDER BY id DESC LIMIT 1", (invoice_id,),
    ).fetchone()
    state = json.loads(event[0]) if event else {"status": "pending", "reason": "Not processed by the agent runner"}
    if invoice["status"] == "posted":
        state = {**state, "status": "completed", "reason": "Posting recorded in the platform"}
    elif any(c["status"] == "waiting_for_client" for c in invoice["cases"]):
        state = {**state, "status": "waiting_for_client"}
    questions = []
    for case in invoice["cases"]:
        for question in get_case(conn, case["id"])["questions"]:
            decision = next((p for p in invoice["postings"] if p["case_id"] == case["id"] and p["status"] == "active"), None)
            questions.append({**question, "status": "resolved" if decision else question["status"],
                              "resolved_by_decision_id": decision["id"] if decision else None})
    return {"invoice_id": invoice_id, **state, "invoice": InvoiceDetail.model_validate(invoice).model_dump(mode="json"),
            "questions": questions, "simulation": True}


def _agent_state(conn: sqlite3.Connection, invoice_id: int, status: str, reason: str, mode: str) -> dict:
    state = {"status": status, "reason": reason, "mode": mode}
    last = conn.execute(
        "SELECT data FROM events WHERE invoice_id = ? AND type = 'agent_state' ORDER BY id DESC LIMIT 1", (invoice_id,),
    ).fetchone()
    if not last or json.loads(last[0]) != state:
        log_event(conn, "system", "agent_state", reason, invoice_id, data=state)
    return agent_result(conn, invoice_id)


def _agent_case(conn: sqlite3.Connection, invoice_id: int, reason: str) -> dict:
    case = conn.execute("SELECT id FROM cases WHERE invoice_id = ? AND status != 'resolved' ORDER BY id DESC LIMIT 1", (invoice_id,)).fetchone()
    if case:
        return get_case(conn, case[0])
    return escalate_invoice(conn, invoice_id, EscalationIn(reason=reason))


def block_agent(conn: sqlite3.Connection, invoice_id: int, reason: str, mode: str) -> dict:
    invoice = _invoice_row(conn, invoice_id)
    if invoice["status"] == "posted":
        return agent_result(conn, invoice_id)
    _agent_case(conn, invoice_id, reason)
    return _agent_state(conn, invoice_id, "blocked", reason, mode)


def process_agent_proposal(conn: sqlite3.Connection, invoice_id: int, proposal: AgentProposal, mode: str, expected: str) -> dict:
    context = agent_context(conn, invoice_id)
    if context_fingerprint(context) != expected:
        raise HTTPException(409, "Case context changed during analysis; rerun the agent")
    invoice = context["invoice"]
    if invoice["status"] == "posted":
        return agent_result(conn, invoice_id)
    if any(c["assignee"] == "accountant" for c in invoice["cases"] if c["status"] != "resolved"):
        return block_agent(conn, invoice_id, "The accountant has taken over this case", mode)
    if any(q["status"] == "open" for q in context["questions"]):
        return _agent_state(conn, invoice_id, "waiting_for_client", "Waiting for the linked client answer", mode)
    if context["policy"] != DEMO_POLICY or "-DEMO-" not in invoice["ksef_number"]:
        return block_agent(conn, invoice_id, "No reviewed policy for this document; only synthetic demo invoices are supported", mode)
    try:
        issued = date.fromisoformat(invoice["issue_date"])
        if not date.fromisoformat(DEMO_POLICY["valid_from"]) <= issued <= date.fromisoformat(DEMO_POLICY["valid_until"]):
            raise ValueError
    except ValueError:
        return block_agent(conn, invoice_id, "Invoice date is outside the synthetic policy period", mode)
    category = invoice_category(invoice["description"])
    if proposal.action == "block" or category == "unsupported" or proposal.category != category:
        return block_agent(conn, invoice_id, "Classification is unsupported or conflicts with the document", mode)

    conditions = {
        "category": category, "policy_version": DEMO_POLICY["version"], "chart_version": DEMO_POLICY["chart_version"],
        "valid_from": DEMO_POLICY["valid_from"], "valid_until": DEMO_POLICY["valid_until"],
    }
    if not invoice["cases"]:
        for match in context["precedents"]:
            precedent = match["precedent"]
            required = {**conditions}
            if category == "vehicle_fuel":
                required["vehicle_plate"] = invoice["vehicle_plate"]
            if match["applicable"] and all(precedent["conditions"].get(k) == v for k, v in required.items()):
                create_posting(conn, invoice_id, PostingIn(
                    account=precedent["account"], vat_deduction_percent=precedent["vat_deduction_percent"],
                    rationale="Reused a matching synthetic decision with current policy conditions", confidence=1,
                    actor="invoice_agent", source="precedent", precedent_id=precedent["id"],
                ))
                return _agent_state(conn, invoice_id, "completed", "Applied a matching conditional precedent", mode)

    if category == "vehicle_fuel":
        plate = invoice["vehicle_plate"]
        vehicle = next((v for v in context["client"]["fleet"] if v["plate"] == plate), None)
        if not plate:
            return block_agent(conn, invoice_id, "No vehicle registration was extracted from the invoice", mode)
        if vehicle is None:
            case = _agent_case(conn, invoice_id, f"Vehicle {plate} is outside the known fleet")
            question = ask_question(conn, case["id"], QuestionIn(
                text=f"Fuel invoice for {plate}: confirm the vehicle, its usage and the business purpose of this purchase.",
            ))
            log_event(conn, "regulations_agent", "context_request", "Vehicle context requested", invoice_id, case["id"], {
                "question_id": question["id"], "missing_context_type": "vehicle_usage",
                "answer_schema": {"required": ["vehicle_plate", "usage", "business_purpose"]},
            })
            return _agent_state(conn, invoice_id, "waiting_for_client", "Vehicle context is missing", mode)
        if vehicle["usage"] != "mixed":
            return block_agent(conn, invoice_id, "Only the synthetic mixed-use fuel rule is supported; additional evidence is required", mode)
        conditions.update(vehicle_plate=plate, vehicle_usage="mixed")

    account = DEMO_POLICY["fuel_account"] if category == "vehicle_fuel" else DEMO_POLICY["it_account"]
    basis = json.dumps({"policy": DEMO_POLICY, "category": category}, sort_keys=True)
    create_posting(conn, invoice_id, PostingIn(
        account=account, vat_deduction_percent=50 if category == "vehicle_fuel" else 100,
        rationale=f"Synthetic fixture policy {DEMO_POLICY['version']}: {category}. {proposal.rationale}",
        confidence=1, actor="regulations_agent" if invoice["cases"] or category == "vehicle_fuel" else "invoice_agent",
        source="regulation" if invoice["cases"] or category == "vehicle_fuel" else "rule",
        legal_basis=basis, reusable=True, conditions=conditions,
    ))
    return _agent_state(conn, invoice_id, "completed", "Synthetic decision recorded with evidence and conditions", mode)


def answer_agent_question(conn: sqlite3.Connection, question_id: int, body: ContextAnswerIn) -> dict:
    question = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    if question is None:
        raise _not_found("Question", question_id)
    case = _case_row(conn, question["case_id"])
    invoice_id = case["invoice_id"]
    data = body.model_dump(exclude_none=True)
    data["vehicle_plate"] = normalize_plate(data.get("vehicle_plate"))
    canonical = json.dumps(data, sort_keys=True)
    if question["status"] == "answered":
        if question["answer"] != canonical:
            raise HTTPException(409, "A different answer is already recorded; use the correction workflow")
        return {"invoice_id": invoice_id, "complete": True, "replayed": True}
    _open_case_row(conn, case["id"])
    request = conn.execute(
        "SELECT data FROM events WHERE type = 'context_request' AND case_id = ? ORDER BY id DESC", (case["id"],),
    ).fetchall()
    if not any(json.loads(r[0]).get("question_id") == question_id for r in request):
        raise HTTPException(409, "This question has no supported structured answer contract")
    missing = [field for field in ("vehicle_plate", "usage", "business_purpose") if not data.get(field)]
    if missing:
        log_event(conn, "client_agent", "context_answer_incomplete", "Client answer needs more facts", invoice_id, case["id"], {"question_id": question_id, "missing": missing})
        return {"invoice_id": invoice_id, "complete": False, "missing": missing}
    invoice = _invoice_row(conn, invoice_id)
    if data["vehicle_plate"] != invoice["vehicle_plate"]:
        raise HTTPException(409, "The answer concerns a different vehicle")
    if case["assignee"] == "accountant":
        raise HTTPException(409, "The accountant has taken over this case")
    answer_question(conn, question_id, AnswerIn(answer=canonical))
    add_vehicle(conn, VehicleIn(plate=data["vehicle_plate"], model=data.get("vehicle_model") or "Client-declared vehicle", usage=data["usage"]))
    add_fact(conn, FactIn(key=f"vehicle_purpose:{data['vehicle_plate']}", value=data["business_purpose"]))
    return {"invoice_id": invoice_id, "complete": True, "replayed": False}


def agent_questions(conn: sqlite3.Connection) -> list[dict]:
    result = []
    for question in list_questions(conn, "open"):
        case = _case_row(conn, question["case_id"])
        invoice = _invoice_row(conn, case["invoice_id"])
        result.append({**question, "invoice_id": invoice["id"], "vehicle_plate": invoice["vehicle_plate"],
                       "answer_schema": {"required": ["vehicle_plate", "usage", "business_purpose"]}})
    return result


def submit_agent_document(conn: sqlite3.Connection, body: InvoiceIn) -> dict:
    row = conn.execute("SELECT id FROM invoices WHERE ksef_number = ?", (body.ksef_number,)).fetchone()
    if row:
        existing = _invoice_row(conn, row[0])
        values = body.model_dump()
        values["vehicle_plate"] = normalize_plate(body.vehicle_plate)
        for key, value in values.items():
            current = Decimal(existing[key]) if key in ("net", "vat", "gross") else existing[key]
            if current != value:
                raise HTTPException(409, "The document identity already exists with different content")
        return dict(existing)
    return insert_invoice(conn, body)
