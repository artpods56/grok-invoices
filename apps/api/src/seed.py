"""Demo data: one past posting already on file, three invoices waiting in a mock KSeF."""

import json
import sqlite3
from decimal import Decimal

from fastapi import HTTPException

from apps.api.src import store
from apps.api.src.db import TABLES
from apps.api.src.schemas import InvoiceIn
from apps.api.src.agent_policy import DEMO_POLICY

COMPANY_VAN = "DW1234A"
UNKNOWN_CAR = "GD9R247"
ORLEN = {"seller_name": "ORLEN S.A.", "seller_nip": "7740001454"}

ACCOUNTS = [
    ("402", "External services"),
    ("403", "Fuel and vehicle expenses"),
]

PAST_INVOICE = InvoiceIn(
    ksef_number="7740001454-20261006-DEMO-000001",
    description="Diesel fuel for a company vehicle",
    vehicle_plate=COMPANY_VAN,
    net=Decimal("350.00"), vat=Decimal("80.50"), gross=Decimal("430.50"),
    issue_date="2026-10-06",
    **ORLEN,
)

KSEF_INBOX = [
    InvoiceIn(
        ksef_number="8992736455-20261103-DEMO-000002",
        seller_name="Demo IT Services Ltd.",
        seller_nip="8992736455",
        description="IT maintenance subscription, November 2026",
        net=Decimal("2000.00"), vat=Decimal("460.00"), gross=Decimal("2460.00"),
        issue_date="2026-11-03",
    ),
    InvoiceIn(
        ksef_number="7740001454-20261104-DEMO-000003",
        description="Diesel fuel for a company vehicle",
        vehicle_plate=COMPANY_VAN,
        net=Decimal("300.00"), vat=Decimal("69.00"), gross=Decimal("369.00"),
        issue_date="2026-11-04",
        **ORLEN,
    ),
    InvoiceIn(
        ksef_number="7740001454-20261105-DEMO-000004",
        description="Diesel fuel for a vehicle",
        vehicle_plate=UNKNOWN_CAR,
        net=Decimal("200.00"), vat=Decimal("46.00"), gross=Decimal("246.00"),
        issue_date="2026-11-05",
        **ORLEN,
    ),
]


def seed(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO client (id, name, nip) VALUES (1, 'Demo Logistics Ltd.', '8943210098')")
    conn.execute(
        "INSERT INTO vehicles (plate, model, usage) VALUES (?, 'VW Transporter', 'mixed')", (COMPANY_VAN,)
    )
    conn.executemany("INSERT INTO accounts (code, name) VALUES (?, ?)", ACCOUNTS)
    store.setup_demo_policy(conn)

    invoice = store.insert_invoice(conn, PAST_INVOICE)
    conditions = {
        "vehicle_usage": "mixed", "vehicle_plate": COMPANY_VAN, "category": "vehicle_fuel",
        "policy_version": DEMO_POLICY["version"], "chart_version": DEMO_POLICY["chart_version"],
        "valid_from": DEMO_POLICY["valid_from"], "valid_until": DEMO_POLICY["valid_until"],
    }
    posting_id = conn.execute(
        "INSERT INTO postings (invoice_id, account, vat_deduction_percent, rationale, confidence, actor, source,"
        " legal_basis, reusable, conditions, status, created_at)"
        " VALUES (?, '403', 50, ?, 1.0, 'accountant', 'accountant', ?, 1, ?, 'active', ?)",
        (
            invoice["id"],
            "Synthetic policy: fuel for the mixed-use VW Transporter, 50% VAT deduction.",
            "VAT Act, Article 86a(1): synthetic fixture reference, not a validated legal opinion",
            json.dumps(conditions),
            invoice["received_at"],
        ),
    ).lastrowid
    conn.execute("UPDATE invoices SET status = 'posted' WHERE id = ?", (invoice["id"],))
    store.log_event(
        conn, "accountant", "precedent_created",
        f"Precedent #{posting_id}: fuel for the VW Transporter, account 403, synthetic VAT deduction 50%",
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
