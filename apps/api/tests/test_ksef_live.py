"""The real flow against KSeF TEST. Not part of CI: run with `uv run pytest -m live`."""

import pytest

from grok_invoices.seed import UNKNOWN_CAR
from grok_invoices.service_layer import services


@pytest.mark.live
def test_issued_invoice_reaches_the_platform_with_its_plate():
    services.start_platform()
    issued = services.issue_demo_invoice()

    # Accepted on the seller's side doesn't mean it's in the buyer's inbox yet.
    for _ in range(12):
        new = [i for i in services.sync_ksef("test") if i.ksef_number == issued.ksef_number]
        if new:
            break
    else:
        pytest.fail("The invoice did not reach permanent storage in time")

    assert new[0].vehicle_plate == UNKNOWN_CAR
    assert new[0].gross == 246
    match = services.search_precedents(new[0].id)[0]
    assert match.applicable is False
    assert UNKNOWN_CAR in match.blockers[0]
