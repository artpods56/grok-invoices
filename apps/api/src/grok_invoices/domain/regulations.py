"""Simplified demo examples. Not verbatim provisions or a maintained legal corpus."""

import re

from pydantic import BaseModel


class Provision(BaseModel):
    citation: str
    text: str


class SearchResult(BaseModel):
    booking_note: str
    provisions: list[Provision]
    validation_status: str = "synthetic_demo"
    authoritative: bool = False
    source_url: str = "https://eli.gov.pl/eli/DU/2004/535/ogl"
    legally_validated_at: str | None = None
    scope_note: str = "Incomplete illustrative paraphrases. Verify official text, amendments, dates and facts before real use."


BOOKING_NOTE = "VAT deduction is a posting decision. The demo fuel invoice's VAT rate remains 23%."

CORPUS: tuple[Provision, ...] = (
    Provision(
        citation="art. 86a ust. 1 ustawy o VAT",
        text=(
            "Demo assumption: mixed-use vehicle fuel, 50% input VAT deduction. "
            "Taxpayer status, taxable business purpose and exclusions still require verification."
        ),
    ),
    Provision(
        citation="art. 86a ust. 3, 4 i 12 ustawy o VAT",
        text=(
            "Exclusive business use can require additional evidence, mileage records and VAT-26. "
            "Exceptions and deadlines must be verified; a company-use declaration alone is insufficient."
        ),
    ),
    Provision(
        citation="art. 86 ust. 1 i art. 88 ustawy o VAT",
        text=(
            "Demo assumption: a purchase without a taxable business purpose has no input VAT deduction. "
            "Private ownership alone does not establish that there is no business use."
        ),
    ),
)

def search(query: str) -> SearchResult:
    """Return corpus entries that share a word with the query. An empty query returns the whole corpus."""
    words = {
        word
        for word in re.findall(r"\w+", query.casefold())
        if len(word) >= 3 or word.isdigit()
    }
    if not words:
        hits = list(CORPUS)
    else:
        hits = [
            item
            for item in CORPUS
            if any(word in f"{item.citation} {item.text}".casefold() for word in words)
        ]
    return SearchResult(booking_note=BOOKING_NOTE, provisions=hits)
