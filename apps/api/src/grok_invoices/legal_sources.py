"""Read official ELI sources. Retrieval is evidence acquisition, never legal approval."""

import hashlib
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser

import httpx

from grok_invoices.domain.errors import Invalid, LegalSourceUnavailable

BASE = "https://api.sejm.gov.pl/eli"
MAX_BYTES = 4 * 1024 * 1024
EXCERPT_CHARS = 20_000
REVIEW_NOTE = (
    "Retrieved from ELI, not validated for a tax decision. Check the relevant text, "
    "amendments, transitional rules, transaction dates and taxpayer facts. "
    "changeDate is a metadata update time, not a provision's effective date."
)


def _eli(value: str) -> str:
    if not re.fullmatch(r"(?:DU|MP)/(?:19|20)\d{2}/[1-9]\d{0,5}", value):
        raise Invalid("Use an ELI identifier such as DU/2004/535, not a URL")
    return value


def _fetch(path: str, params: dict | None = None, *, html: bool = False) -> tuple[bytes, dict]:
    # Only this fixed HTTPS origin is reachable. Redirects cannot escape it.
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            with client.stream("GET", f"{BASE}/{path}", params=params) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                expected = "text/html" if html else "application/json"
                if expected not in content_type:
                    raise LegalSourceUnavailable("ELI returned an unexpected content type")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise LegalSourceUnavailable("ELI response exceeds the 4 MB limit; use a smaller fragment")
                    chunks.append(chunk)
                content = b"".join(chunks)
                if not content.strip():
                    raise LegalSourceUnavailable("ELI returned an empty body; no legal evidence was acquired")
                evidence = {
                    "url": str(response.url),
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "validation_status": "requires_review",
                    "review_note": REVIEW_NOTE,
                }
                return content, evidence
    except httpx.HTTPError as error:
        # Do not echo upstream response bodies or credentials from the environment.
        raise LegalSourceUnavailable("ELI request failed; keep the case blocked and retry later") from error


def _json(path: str, params: dict | None = None) -> tuple[dict, dict]:
    content, evidence = _fetch(path, params)
    try:
        data = json.loads(content)
    except (ValueError, UnicodeError) as error:
        raise LegalSourceUnavailable("ELI returned invalid JSON") from error
    if not isinstance(data, dict):
        raise LegalSourceUnavailable("ELI returned an unexpected JSON shape")
    return data, evidence


def get_act(eli: str) -> dict:
    eli = _eli(eli)
    data, evidence = _json(f"acts/{eli}")
    publisher, year, position = eli.split("/")
    if (data.get("publisher"), data.get("year"), data.get("pos")) != (publisher, int(year), int(position)) or not data.get("title"):
        raise LegalSourceUnavailable("ELI metadata does not identify the requested act")
    return {"eli": eli, "publication_url": f"https://eli.gov.pl/eli/{eli}/ogl", "metadata": data, **evidence}


def _page(path: str, params: dict) -> dict:
    data, evidence = _json(path, params)
    items = data.get("items")
    count, offset, total = data.get("count"), data.get("offset"), data.get("totalCount")
    if (
        not isinstance(items, list)
        or any(type(number) is not int or number < 0 for number in (count, offset, total))
        or count != len(items) or offset != params["offset"] or count > params["limit"]
        or (count > 0 and offset + count > total) or (count == 0 and offset < total)
        or any(not isinstance(item, dict) or not item.get("title") for item in items)
    ):
        raise LegalSourceUnavailable("ELI pagination is incomplete or inconsistent; do not advance a checkpoint")
    next_offset = offset + count if offset + count < total else None
    return {
        **data, **evidence, "next_offset": next_offset,
        "coverage_complete": offset == 0 and next_offset is None,
        "checkpoint_note": (
            "Read every page from offset 0 with the same since/filter before acknowledging coverage. "
            "Totals can change during paging: overlap the next scan and deduplicate by act and changeDate. "
            "This tool does not persist or advance a checkpoint."
        ),
    }


def _pagination(offset: int, limit: int) -> None:
    if offset < 0 or not 1 <= limit <= 500:
        raise Invalid("offset must be nonnegative and limit must be between 1 and 500")


def search_acts(title: str, offset: int = 0, limit: int = 25) -> dict:
    _pagination(offset, limit)
    if not title.strip() or len(title) > 200:
        raise Invalid("Provide a title query between 1 and 200 characters")
    # Include repealed and future acts too; an inForce filter would hide relevant history.
    return _page("acts/search", {"title": title, "offset": offset, "limit": limit})


def check_updates(since: str, offset: int = 0, limit: int = 100) -> dict:
    _pagination(offset, limit)
    # Match the publisher's timezone-free timestamp without inventing a UTC conversion.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", since):
        raise Invalid("since must use ELI's timestamp format YYYY-MM-DDTHH:MM:SS without a timezone suffix")
    try:
        datetime.fromisoformat(since)
    except ValueError as error:
        raise Invalid("since is not a valid calendar timestamp") from error
    return _page("changes/acts", {"since": since, "offset": offset, "limit": limit})


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def read_text(eli: str, article: str | None = None, offset: int = 0) -> dict:
    eli = _eli(eli)
    if offset < 0:
        raise Invalid("offset must be nonnegative")
    if article is not None and not re.fullmatch(r"[1-9]\d{0,3}[a-z]{0,2}", article):
        raise Invalid("article must be a number with an optional suffix, for example 86a")
    path = f"acts/{eli}/text.html" + (f"/art={article}" if article else "")
    content, evidence = _fetch(path, html=True)
    try:
        parser = _Text()
        parser.feed(content.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as error:
        raise LegalSourceUnavailable("ELI text could not be decoded") from error
    text = "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())
    recognized = re.search(r"\b(?:Art\.?\s*\d+[a-z]*|USTAWA|ROZPORZĄDZENIE|OBWIESZCZENIE)\b", text, re.I)
    if len(text) < 30 or not recognized or (article and not re.search(rf"\bArt\.?\s*{re.escape(article)}\s*[.\s]", text, re.I)):
        raise LegalSourceUnavailable("ELI supplied no recognizable requested provision; use a verified publication or block")
    excerpt = text[offset:offset + EXCERPT_CHARS]
    if not excerpt:
        raise Invalid("offset is past the available text")
    return {
        "eli": eli, "article": article, "text": excerpt, "offset": offset,
        "total_chars": len(text),
        "next_offset": offset + len(excerpt) if offset + len(excerpt) < len(text) else None,
        "excerpt_complete": offset == 0 and len(excerpt) == len(text),
        "version_note": "Text attached to this ELI publication; not a guaranteed consolidation as of the invoice date.",
        **evidence,
    }
