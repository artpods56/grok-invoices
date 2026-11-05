"""Demo data, built as real FA(3) through ksef2 so fixtures and live KSeF share one code path."""

from datetime import date, datetime
from decimal import Decimal

from grok_invoices.domain.models import (
    Account, Client, Event, Invoice, Posting, PrecedentConditions, ReceivedDocument, Vehicle,
)
from grok_invoices.ksef import DEMO_SELLER_ADDRESS, DEMO_SELLER_NAME, DEMO_SELLER_NIP, build_invoice_xml
from grok_invoices.service_layer.unit_of_work import UnitOfWork
from grok_invoices.settings import get_settings

CLIENT_NIP = "8943210057"
CLIENT_NAME = "Demo Logistyka sp. z o.o."
COMPANY_VAN = "DW 1234A"
UNKNOWN_CAR = "GD 9R247"  # The stage demo depends on this plate staying off the fleet.
IT_SELLER_NIP = "8992736457"


def _fuel(number: str, issued: date, plate: str, litres: str) -> bytes:
    return build_invoice_xml(
        seller_nip=DEMO_SELLER_NIP, seller_name=DEMO_SELLER_NAME, seller_address=DEMO_SELLER_ADDRESS,
        buyer_nip=CLIENT_NIP, buyer_name=CLIENT_NAME, number=number, issued=issued,
        line=f"ON Ekodiesel, tankowanie {plate}", unit="l", quantity=Decimal(litres), unit_price=Decimal("5.00"), plate=plate,
    )


def fixture_inbox() -> list[ReceivedDocument]:
    """The three-invoice path, for tests and as a stage fallback if KSeF TEST is down."""
    it_service = build_invoice_xml(
        seller_nip=IT_SELLER_NIP, seller_name="Softwarehouse Wrocław sp. z o.o.", seller_address="ul. Rynek 1, 50-101 Wrocław",
        buyer_nip=CLIENT_NIP, buyer_name=CLIENT_NAME, number="FV/2026/11/017", issued=date(2026, 11, 3),
        line="Abonament za utrzymanie systemu IT, listopad 2026", unit="szt", quantity=Decimal("1"), unit_price=Decimal("2000.00"),
    )
    return [
        ReceivedDocument(f"{IT_SELLER_NIP}-20261103-DEMO-000002", it_service),
        ReceivedDocument(f"{DEMO_SELLER_NIP}-20261104-DEMO-000003", _fuel("ON/2026/11/104", date(2026, 11, 4), COMPANY_VAN, "60")),
        ReceivedDocument(f"{DEMO_SELLER_NIP}-20261105-DEMO-000004", _fuel("ON/2026/11/105", date(2026, 11, 5), UNKNOWN_CAR, "40")),
    ]


def populate(uow: UnitOfWork, now: datetime) -> None:
    uow.clients.add(Client(
        name=CLIENT_NAME,
        nip=CLIENT_NIP,
        phone=get_settings().demo_client_phone,
        ksef_since=now,
        fleet=[Vehicle(plate=COMPANY_VAN, model="VW Transporter", usage="mixed")],
        accounts=[
            Account(code="402", name="Usługi obce"),
            Account(code="403", name="Paliwo i eksploatacja pojazdów"),
        ],
    ))
    invoice = uow.invoices.add(Invoice.receive(
        ReceivedDocument(f"{DEMO_SELLER_NIP}-20261006-DEMO-000001", _fuel("ON/2026/10/006", date(2026, 10, 6), COMPANY_VAN, "70")),
        now,
    ))
    invoice.mark_posted()
    posting = uow.postings.add(Posting(
        invoice_id=invoice.id,
        account="403",
        vat_deduction_percent=50,
        deductible_vat=invoice.deductible_vat(50),
        rationale="Paliwo do firmowego VW Transportera w użytku mieszanym: odliczenie 50% VAT.",
        confidence=1.0,
        actor="accountant",
        source="accountant",
        legal_basis="Art. 86a ust. 1 ustawy o VAT",
        reusable=True,
        conditions=PrecedentConditions(vehicle_usage="mixed"),
        created_at=now,
    ))
    uow.events.add(Event(
        at=now, actor="system", type="demo_reset", summary="Dane startowe przywrócone",
    ))
    uow.events.add(Event(
        at=now, actor="accountant", type="precedent_created",
        summary=f"Precedens #{posting.id}: paliwo Orlen do VW Transportera → konto 403, VAT 50%",
        invoice_id=invoice.id, data={"posting_id": posting.id},
    ))
