"""The unit of work's guarantees, and the rule that keeps the layers apart."""

import ast
from pathlib import Path

import pytest

import grok_invoices
from grok_invoices.domain.errors import Invalid
from grok_invoices.domain.models import Event, Invoice, ReceivedDocument
from grok_invoices.service_layer import services
from grok_invoices.service_layer.unit_of_work import UnitOfWork
from grok_invoices.seed import UNKNOWN_CAR, fixture_inbox

PACKAGE = Path(grok_invoices.__file__).parent


@pytest.fixture(autouse=True)
def platform():
    services.start_platform()


def test_changes_save_on_commit_without_an_explicit_save():
    with UnitOfWork() as uow:
        uow.client.phone = "+48123"
    with UnitOfWork(write=False) as uow:
        assert uow.client.phone == "+48123"


def test_an_exception_rolls_back_everything_in_the_block():
    before = len(services.list_events())
    with pytest.raises(RuntimeError):
        with UnitOfWork() as uow:
            uow.client.phone = "+48999"
            uow.events.add(Event(at=services._now(), actor="system", type="demo_reset", summary="x"))
            raise RuntimeError
    assert len(services.list_events()) == before
    assert services.get_client().phone != "+48999"


def test_a_read_only_unit_of_work_never_persists_changes():
    with UnitOfWork(write=False) as uow:
        uow.client.phone = "+48777"
    assert services.get_client().phone != "+48777"


def test_a_stored_invoice_reloads_with_its_ksef_document():
    document = fixture_inbox()[2]
    invoice_id = services.ingest_documents([document])[0].id
    with UnitOfWork(write=False) as uow:
        invoice = uow.invoices.require(invoice_id)
    assert invoice.vehicle_plate == UNKNOWN_CAR
    assert invoice.document.seller.tax_id == "1132511471"
    assert invoice.deductible_vat(50) == invoice.vat / 2


def test_invalid_xml_is_refused_at_the_door():
    with pytest.raises(Invalid):
        Invoice.receive(ReceivedDocument("x", b"<not-fa3/>"), services._now())


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize(
    ("layer", "forbidden"),
    [
        ("domain", ("fastapi", "sqlite3", "grok_invoices.service_layer", "grok_invoices.entrypoints", "grok_invoices.ksef", "grok_invoices.settings")),
        ("service_layer", ("fastapi", "grok_invoices.entrypoints", "mcp")),
    ],
)
def test_layers_only_depend_inward(layer, forbidden):
    for path in (PACKAGE / layer).rglob("*.py"):
        for name in _imports(path):
            assert not name.startswith(forbidden), f"{path.relative_to(PACKAGE)} must not import {name}"
