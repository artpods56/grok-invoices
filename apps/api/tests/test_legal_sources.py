"""Official-source acquisition and failure handling, using mocked HTTP only."""

import hashlib

import httpx
import pytest

from grok_invoices import legal_sources
from grok_invoices.domain.errors import Invalid, LegalSourceUnavailable


@pytest.fixture
def upstream(monkeypatch):
    original = httpx.Client

    def install(handler):
        def client(**kwargs):
            return original(transport=httpx.MockTransport(handler), **kwargs)
        monkeypatch.setattr(legal_sources.httpx, "Client", client)

    return install


def test_metadata_has_provenance_without_claiming_legal_validation(upstream):
    def handler(request):
        assert str(request.url) == "https://api.sejm.gov.pl/eli/acts/DU/2004/535"
        return httpx.Response(200, json={
            "publisher": "DU", "year": 2004, "pos": 535, "title": "VAT Act",
            "changeDate": "2026-11-03T00:00:00", "entryIntoForce": "2004-04-20",
            "references": {"amendments": [{"id": "DU/2026/1"}]},
        })

    upstream(handler)
    result = legal_sources.get_act("DU/2004/535")
    assert result["validation_status"] == "requires_review"
    assert result["retrieved_at"].endswith("+00:00")
    assert len(result["sha256"]) == 64
    assert result["metadata"]["changeDate"] != result["metadata"]["entryIntoForce"]
    assert result["metadata"]["references"]


@pytest.mark.parametrize("value", ["http://127.0.0.1/", "DU/2004/535/../../secret", "DU/2004/535?url=private", "DU/2004/0"])
def test_an_arbitrary_url_never_reaches_the_network(monkeypatch, value):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid identifiers must fail before HTTP")
    monkeypatch.setattr(legal_sources, "_fetch", forbidden)
    with pytest.raises(Invalid):
        legal_sources.get_act(value)


@pytest.mark.parametrize("response", [
    httpx.Response(200, text="", headers={"content-type": "text/html"}),
    httpx.Response(200, text="<html><body>Not found</body></html>", headers={"content-type": "text/html"}),
    httpx.Response(200, text="<p>Art. 87. This is a different article with enough content.</p>", headers={"content-type": "text/html"}),
    httpx.Response(302, headers={"location": "http://127.0.0.1/private"}),
    httpx.Response(503, text="Internal source details"),
])
def test_empty_wrong_or_failed_provisions_are_not_evidence(upstream, response):
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return response
    upstream(handler)
    with pytest.raises(LegalSourceUnavailable):
        legal_sources.read_text("DU/2004/535", "86a")
    assert len(calls) == 1


def test_text_excerpts_are_explicit_and_hash_the_complete_acquired_body(upstream):
    content = ("<p>Art. 86a. " + "Example legal text. " * 1500 + "</p><script>hidden-secret</script>").encode()
    upstream(lambda request: httpx.Response(200, content=content, headers={"content-type": "text/html"}))
    first = legal_sources.read_text("DU/2004/535", "86a")
    assert first["sha256"] == hashlib.sha256(content).hexdigest()
    assert "hidden-secret" not in first["text"]
    assert len(first["text"]) == 20_000
    assert first["excerpt_complete"] is False
    assert first["next_offset"] == 20_000
    last = legal_sources.read_text("DU/2004/535", "86a", first["next_offset"])
    assert last["next_offset"] is None
    assert last["excerpt_complete"] is False


def test_changes_require_every_page_and_do_not_persist_a_checkpoint(upstream):
    calls = []
    def handler(request):
        calls.append(request)
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json={
            "items": [{"title": "A changed act", "changeDate": "2026-11-05T01:00:00"}],
            "count": 1, "offset": offset, "totalCount": 2,
        })
    upstream(handler)
    first = legal_sources.check_updates("2026-11-04T00:00:00", limit=1)
    assert first["next_offset"] == 1
    assert first["coverage_complete"] is False
    last = legal_sources.check_updates("2026-11-04T00:00:00", offset=1, limit=1)
    assert last["next_offset"] is None
    assert last["coverage_complete"] is False
    assert calls[0].url.params["since"] == calls[1].url.params["since"]


@pytest.mark.parametrize("data", [
    {"items": [], "count": 0, "offset": 0, "totalCount": 3},
    {"items": [], "count": 1, "offset": 0, "totalCount": 1},
    {"items": [], "count": 0, "offset": 8, "totalCount": 0},
    {"items": [], "count": 0, "offset": 0},
])
def test_inconsistent_change_pages_fail_closed(upstream, data):
    upstream(lambda request: httpx.Response(200, json=data))
    with pytest.raises(LegalSourceUnavailable):
        legal_sources.check_updates("2026-11-04T00:00:00")


def test_search_keeps_historical_and_future_acts(upstream):
    def handler(request):
        assert request.url.params["title"] == "VAT"
        assert "inForce" not in request.url.params
        return httpx.Response(200, json={"items": [], "count": 0, "offset": 0, "totalCount": 0})
    upstream(handler)
    assert legal_sources.search_acts("VAT")["coverage_complete"] is True


@pytest.mark.parametrize("since", ["2026-11-05", "2026-13-05T00:00:00", "2026-11-05T00:00:00Z"])
def test_publisher_timestamp_must_not_invent_a_timezone(since):
    with pytest.raises(Invalid):
        legal_sources.check_updates(since)


def test_oversized_or_misidentified_metadata_is_rejected(upstream, monkeypatch):
    upstream(lambda request: httpx.Response(200, json={"title": "Different act", "publisher": "DU", "year": 2004, "pos": 999}))
    with pytest.raises(LegalSourceUnavailable, match="requested act"):
        legal_sources.get_act("DU/2004/535")
    monkeypatch.setattr(legal_sources, "MAX_BYTES", 5)
    with pytest.raises(LegalSourceUnavailable, match="limit"):
        legal_sources.get_act("DU/2004/535")
