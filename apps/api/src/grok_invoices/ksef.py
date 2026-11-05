"""KSeF TEST through ksef2. These calls reach the network: never make them inside a UnitOfWork."""

from collections.abc import Callable, Collection
from datetime import date, datetime
from decimal import Decimal

from ksef2 import Client, Environment, FormSchema, KSeFException
from ksef2.fa3 import InvoiceBuilder, VatRate
from ksef2.models import InvoiceMetadataParams, InvoicesFilter

from grok_invoices.domain.errors import KsefUnavailable
from grok_invoices.domain.models import VEHICLE_PLATE_KEY, ReceivedDocument

DEMO_SELLER_NIP = "1132511471"
DEMO_SELLER_NAME = "ORLEN S.A."
DEMO_SELLER_ADDRESS = "ul. Chemików 7, 09-411 Płock"
_REQUEST_TIMEOUT = 60.0


def _with_ksef[T](call: Callable[[Client], T]) -> T:
    try:
        with Client(Environment.TEST) as client:
            return call(client)
    except KSeFException as error:
        raise KsefUnavailable(f"KSeF request failed: {error}") from error


def fetch_new(
    nip: str, since: datetime, known: Collection[str], *, ksef_token: str | None = None,
) -> list[ReceivedDocument]:
    """Download purchase invoices in permanent storage since `since`, skipping `known` KSeF numbers.

    Permanent storage matters: an invoice accepted on the seller's side may not be in the
    buyer's inbox yet. Metadata has no line items or plate, so each invoice is downloaded.

    A stored KSeF token logs in with `with_token`. Without one, the TEST certificate is used.
    The caller decrypts the token before this call. This function reaches the network.
    """

    def fetch(client: Client) -> list[ReceivedDocument]:
        if ksef_token:
            auth = client.authentication.with_token(ksef_token=ksef_token, nip=nip)
        else:
            auth = client.authentication.with_test_certificate(nip=nip)
        filters = InvoicesFilter.for_buyer(date_from=since, date_type="permanent_storage")
        params = InvoiceMetadataParams(page_size=100, sort_order="asc")
        return [
            ReceivedDocument(row.ksef_number, auth.invoices.download(row.ksef_number, timeout=_REQUEST_TIMEOUT))
            for row in auth.invoices.search(filters, params)
            if row.ksef_number not in known
        ]

    return _with_ksef(fetch)


def build_invoice_xml(
    *, seller_nip: str, seller_name: str, seller_address: str, buyer_nip: str, buyer_name: str,
    number: str, issued: date, line: str, unit: str, quantity: Decimal, unit_price: Decimal, plate: str | None = None,
) -> bytes:
    builder = (
        InvoiceBuilder()
        .header(system_info="grok-invoices")
        .seller(name=seller_name, tax_id=seller_nip, country_code="PL", address_line_1=seller_address)
        .buyer(name=buyer_name, tax_id=buyer_nip, country_code="PL", address_line_1="ul. Testowa 1, 50-001 Wrocław")
        .standard()
        .issue_place("Wrocław")
        .issue_date(issued)
        .invoice_number(number)
    )
    if plate:
        builder = builder.add_description(key=VEHICLE_PLATE_KEY, value=plate)
    return (
        builder.rows()
        .add_line(name=line, unit_of_measure=unit, quantity=quantity, unit_price_net=unit_price, vat_rate=VatRate.VAT_23)
        .done()
        .done()
        .to_xml()
        .encode()
    )


def issue_fuel_invoice(*, buyer_nip: str, buyer_name: str, plate: str, number: str, issued: date) -> str:
    """Issue the stage demo's invoice as the TEST seller and return its KSeF number."""
    xml = build_invoice_xml(
        seller_nip=DEMO_SELLER_NIP, seller_name=DEMO_SELLER_NAME, seller_address=DEMO_SELLER_ADDRESS,
        buyer_nip=buyer_nip, buyer_name=buyer_name, number=number, issued=issued,
        line=f"ON Ekodiesel, tankowanie {plate}", unit="l", quantity=Decimal("40"), unit_price=Decimal("5.00"), plate=plate,
    )

    def send(client: Client) -> str:
        auth = client.authentication.with_test_certificate(nip=DEMO_SELLER_NIP)
        with auth.online_session(form_code=FormSchema.FA3) as session:
            return session.send_invoice(xml).wait(timeout=_REQUEST_TIMEOUT).ksef_number

    return _with_ksef(send)
