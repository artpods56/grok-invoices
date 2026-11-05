"""Platform state and the rules agents can't bypass. Every write adds a timeline event."""

import json
import re
import sqlite3
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException

from apps.api.src.schemas import AnswerIn, CorrectionIn, EscalationIn, FactIn, InvoiceIn, PostingIn, QuestionIn, VehicleIn


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
    required_usage = conditions.get("vehicle_usage")
    if not required_usage:
        return []
    plate = invoice["vehicle_plate"]
    if not plate:
        return ["the invoice does not name a vehicle"]
    vehicle = conn.execute("SELECT usage FROM vehicles WHERE plate = ?", (plate,)).fetchone()
    if vehicle is None:
        return [f"vehicle {plate} is not on the client's fleet"]
    if vehicle["usage"] != required_usage:
        return [f"vehicle {plate} has usage '{vehicle['usage']}', the precedent requires '{required_usage}'"]
    return []


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
        f"Nowa faktura {body.ksef_number}: {body.seller_name}, {body.gross} PLN", invoice_id,
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
        blockers = precedent_blockers(conn, invoice, json.loads(precedent["conditions"]))
        if blockers:
            raise HTTPException(409, f"Precedent does not apply: {'; '.join(blockers)}")

    case_id = case["id"] if case is not None else None
    posting_id = _insert_posting(conn, invoice_id, case_id, body, body.actor, body.source, body.confidence, body.precedent_id)
    conn.execute("UPDATE invoices SET status = 'posted' WHERE id = ?", (invoice_id,))
    if case is not None:
        conn.execute("UPDATE cases SET status = 'resolved', resolved_at = ? WHERE id = ?", (_now(), case_id))

    how = {
        "rule": "dekretacja bezpośrednia",
        "precedent": f"zastosowano precedens #{body.precedent_id}",
        "regulation": "decyzja na podstawie przepisów",
        "accountant": "decyzja księgowej",
    }[body.source]
    log_event(
        conn, body.actor, "invoice_posted",
        f"Faktura {invoice['ksef_number']} → konto {body.account}, VAT {body.vat_deduction_percent}% ({how})",
        invoice_id, case_id,
        {
            "posting_id": posting_id, "source": body.source, "confidence": body.confidence,
            "rationale": body.rationale, "precedent_id": body.precedent_id, "legal_basis": body.legal_basis,
        },
    )
    if body.reusable:
        log_event(
            conn, body.actor, "precedent_created", f"Nowy precedens #{posting_id}: {body.rationale}",
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
        f"Księgowa poprawiła dekretację #{posting_id} → konto {body.account}, VAT {body.vat_deduction_percent}%",
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
    log_event(conn, body.actor, "case_opened", f"Eskalacja faktury {invoice['ksef_number']}: {body.reason}", invoice_id, case_id)
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
    log_event(conn, body.actor, "question_asked", f"Pytanie do klienta: {body.text}", case["invoice_id"], case_id, {"question_id": question_id})
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
    log_event(conn, body.actor, "question_answered", f"Odpowiedź klienta: {body.answer}", case["invoice_id"], case["id"], {"question_id": question_id})
    return dict(conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone())


def take_over_case(conn: sqlite3.Connection, case_id: int) -> dict[str, Any]:
    case = _open_case_row(conn, case_id)
    conn.execute("UPDATE cases SET assignee = 'accountant' WHERE id = ?", (case_id,))
    log_event(conn, "accountant", "case_taken_over", f"Księgowa przejęła sprawę #{case_id}", case["invoice_id"], case_id)
    return get_case(conn, case_id)


def add_fact(conn: sqlite3.Connection, body: FactIn) -> dict[str, Any]:
    fact_id = conn.execute(
        "INSERT INTO client_facts (key, value, source, created_at) VALUES (?, ?, ?, ?)",
        (body.key, body.value, body.source, _now()),
    ).lastrowid
    log_event(conn, body.source, "client_fact_added", f"Nowy fakt o firmie: {body.key} = {body.value}", data={"fact_id": fact_id})
    return get_client(conn)


def add_vehicle(conn: sqlite3.Connection, body: VehicleIn) -> dict[str, Any]:
    plate = normalize_plate(body.plate)
    conn.execute(
        "INSERT INTO vehicles (plate, model, usage) VALUES (?, ?, ?)"
        " ON CONFLICT (plate) DO UPDATE SET model = excluded.model, usage = excluded.usage",
        (plate, body.model, body.usage),
    )
    log_event(conn, body.actor, "vehicle_saved", f"Flota: {plate} ({body.model}, użytek: {body.usage})", data={"plate": plate})
    return get_client(conn)
