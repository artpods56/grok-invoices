"""Demo data: one past posting already on file, three invoices waiting in a mock KSeF."""

import json
import sqlite3
from decimal import Decimal

from fastapi import HTTPException

from app import store
from app.db import TABLES
from app.schemas import InvoiceIn

COMPANY_VAN = "DW1234A"
UNKNOWN_CAR = "DW9876C"
ORLEN = {"seller_name": "ORLEN S.A.", "seller_nip": "7740001454"}

ACCOUNTS = [
    ("402", "Usługi obce"),
    ("403", "Paliwo i eksploatacja pojazdów"),
]

PAST_INVOICE = InvoiceIn(
    ksef_number="7740001454-20261006-DEMO-000001",
    description="Paliwo ON, tankowanie pojazdu służbowego",
    vehicle_plate=COMPANY_VAN,
    net=Decimal("350.00"), vat=Decimal("80.50"), gross=Decimal("430.50"),
    issue_date="2026-10-06",
    **ORLEN,
)

KSEF_INBOX = [
    InvoiceIn(
        ksef_number="8992736455-20261103-DEMO-000002",
        seller_name="Softwarehouse Wrocław sp. z o.o.",
        seller_nip="8992736455",
        description="Abonament za utrzymanie systemu IT, listopad 2026",
        net=Decimal("2000.00"), vat=Decimal("460.00"), gross=Decimal("2460.00"),
        issue_date="2026-11-03",
    ),
    InvoiceIn(
        ksef_number="7740001454-20261104-DEMO-000003",
        description="Paliwo ON, tankowanie pojazdu służbowego",
        vehicle_plate=COMPANY_VAN,
        net=Decimal("300.00"), vat=Decimal("69.00"), gross=Decimal("369.00"),
        issue_date="2026-11-04",
        **ORLEN,
    ),
    InvoiceIn(
        ksef_number="7740001454-20261105-DEMO-000004",
        description="Paliwo ON, tankowanie pojazdu",
        vehicle_plate=UNKNOWN_CAR,
        net=Decimal("250.00"), vat=Decimal("57.50"), gross=Decimal("307.50"),
        issue_date="2026-11-05",
        **ORLEN,
    ),
]


def seed(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO client (id, name, nip) VALUES (1, 'Demo Logistyka sp. z o.o.', '8943210098')")
    conn.execute(
        "INSERT INTO vehicles (plate, model, usage) VALUES (?, 'VW Transporter', 'mixed')", (COMPANY_VAN,)
    )
    conn.executemany("INSERT INTO accounts (code, name) VALUES (?, ?)", ACCOUNTS)

    invoice = store.insert_invoice(conn, PAST_INVOICE)
    conditions = {"vehicle_usage": "mixed"}
    posting_id = conn.execute(
        "INSERT INTO postings (invoice_id, account, vat_deduction_percent, rationale, confidence, actor, source,"
        " legal_basis, reusable, conditions, status, created_at)"
        " VALUES (?, '403', 50, ?, 1.0, 'accountant', 'accountant', ?, 1, ?, 'active', ?)",
        (
            invoice["id"],
            "Paliwo do firmowego VW Transportera w użytku mieszanym: odliczenie 50% VAT.",
            "Art. 86a ust. 1 ustawy o VAT",
            json.dumps(conditions),
            invoice["received_at"],
        ),
    ).lastrowid
    conn.execute("UPDATE invoices SET status = 'posted' WHERE id = ?", (invoice["id"],))
    store.log_event(
        conn, "accountant", "precedent_created",
        f"Precedens #{posting_id}: paliwo Orlen do VW Transportera → konto 403, VAT 50%",
        invoice["id"], data={"posting_id": posting_id, "conditions": conditions},
    )


def seed_if_empty(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM client").fetchone() is None:
        seed(conn)


def reset(conn: sqlite3.Connection) -> None:
    for table in TABLES:
        conn.execute(f"DELETE FROM {table}")
    seed(conn)


def sync_mock_ksef(conn: sqlite3.Connection) -> list[dict]:
    """Stands in for a real KSeF fetch. Syncing twice adds nothing new."""
    fetched = []
    for invoice in KSEF_INBOX:
        try:
            fetched.append(store.insert_invoice(conn, invoice))
        except HTTPException as error:
            if error.status_code != 409:
                raise
    return fetched
