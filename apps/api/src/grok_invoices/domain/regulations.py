"""The VAT provisions the regulations agent may cite. No others."""

import re

from pydantic import BaseModel


class Provision(BaseModel):
    citation: str
    text: str


class SearchResult(BaseModel):
    booking_note: str
    provisions: list[Provision]


BOOKING_NOTE = "Odliczenie VAT jest decyzją księgowania. Stawka VAT na fakturze zostaje 23%."

CORPUS: tuple[Provision, ...] = (
    Provision(
        citation="art. 86a ust. 1 ustawy o VAT",
        text=(
            "Pojazd w użytku mieszanym: 50% odliczenia VAT naliczonego "
            "od wydatków na pojazd i na paliwo."
        ),
    ),
    Provision(
        citation="art. 86a ust. 3, 4 i 12 ustawy o VAT",
        text=(
            "Odliczenie 100% tylko przy wyłącznym użytkowaniu w działalności, "
            "po złożeniu VAT-26 i prowadzeniu ewidencji przebiegu."
        ),
    ),
    Provision(
        citation="art. 86 ust. 1 i art. 88 ustawy o VAT",
        text=(
            "Samochód prywatny nieużywany w działalności nie daje odliczenia. "
            "Wydatek nie ma związku z działalnością opodatkowaną."
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
