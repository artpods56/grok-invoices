"""Accounting rules enforced by the platform, whatever an agent's model decides."""

import re
from collections.abc import Iterable

from grok_invoices.domain.errors import Conflict, Invalid
from grok_invoices.domain.models import Actor, Client, Invoice, PostingSource, PrecedentConditions, normalize_plate

POSTING_ACTORS: tuple[Actor, ...] = ("invoice_agent", "regulations_agent", "accountant")


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) >= 3 and not t.isdigit()}


def similarity(a: Invoice, b: Invoice) -> float:
    """How alike two invoices look, from 0 to 1. Looking alike never makes a precedent apply."""
    ta, tb = _tokens(a.description), _tokens(b.description)
    overlap = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return round(0.5 * (a.seller_nip == b.seller_nip) + 0.5 * overlap, 3)


def plates_on_hold(open_case_invoices: Iterable[Invoice], excluding: Invoice) -> set[str]:
    """Vehicles the client is already being asked about, so nothing else about them proceeds."""
    return {
        normalize_plate(invoice.vehicle_plate)
        for invoice in open_case_invoices
        if invoice.vehicle_plate and invoice.id != excluding.id
    }


def hold_blockers(invoice: Invoice, on_hold: set[str]) -> list[str]:
    plate = invoice.vehicle_plate
    if plate and normalize_plate(plate) in on_hold:
        return [f"waiting for the client's answer about vehicle {plate}"]
    return []


def precedent_blockers(
    invoice: Invoice, conditions: PrecedentConditions, client: Client, on_hold: set[str]
) -> list[str]:
    """Why a precedent can't be reused on this invoice, however similar it looks."""
    blockers = hold_blockers(invoice, on_hold)
    plate = invoice.vehicle_plate
    if conditions.vehicle_plate and (not plate or normalize_plate(plate) != normalize_plate(conditions.vehicle_plate)):
        blockers.append(f"the precedent only applies to vehicle {conditions.vehicle_plate}")
    if conditions.vehicle_usage:
        if not plate:
            blockers.append("the invoice does not name a vehicle")
        elif (vehicle := client.vehicle(plate)) is None:
            blockers.append(f"vehicle {plate} is not on the client's fleet")
        elif vehicle.usage != conditions.vehicle_usage:
            blockers.append(f"vehicle {plate} has usage '{vehicle.usage}', the precedent requires '{conditions.vehicle_usage}'")
    return blockers


def ensure_posting_allowed(
    invoice: Invoice, actor: Actor, source: PostingSource, has_open_case: bool,
    precedent_id: int | None, legal_basis: str | None,
) -> None:
    if actor not in POSTING_ACTORS:
        raise Invalid(f"{actor} can't post invoices")
    if source == "accountant" and actor != "accountant":
        raise Invalid("Only the accountant can use source 'accountant'")
    if source == "regulation" and not legal_basis:
        raise Invalid("A regulation decision needs a legal_basis")
    if source == "precedent" and precedent_id is None:
        raise Invalid("A precedent posting needs a precedent_id")
    if source != "precedent" and precedent_id is not None:
        raise Invalid("precedent_id is only valid with source 'precedent'")
    if source == "rule" and invoice.vehicle_plate:
        # Wrong VAT on a vehicle is a liability, so it's never decided by a plain rule.
        raise Conflict(f"Invoice names vehicle {invoice.vehicle_plate}: use a precedent or escalate it")
    if source == "regulation" and not has_open_case:
        raise Conflict("A regulation decision needs an open case: escalate the invoice first")


_NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
DOCUMENT_BYTE_LIMIT = 1024 * 1024


def onboarding_identity(nip: str, company_name: str) -> tuple[str, str]:
    """The NIP and company name to store. A NIP is 10 digits whose checksum matches.

    The checksum is the weighted sum of the first nine digits, mod 11. Weights are
    6, 5, 7, 2, 3, 4, 5, 6, 7. A remainder of 10 cannot be a check digit.
    Spaces and hyphens in the NIP are ignored.
    """
    digits = re.sub(r"[\s-]", "", nip.strip())
    if not re.fullmatch(r"\d{10}", digits):
        raise Invalid("NIP must be 10 digits")
    total = sum(int(digit) * weight for digit, weight in zip(digits[:9], _NIP_WEIGHTS, strict=True))
    checksum = total % 11
    if checksum == 10 or checksum != int(digits[9]):
        raise Invalid("NIP checksum is invalid")
    name = company_name.strip()
    if not name:
        raise Invalid("Company name is empty")
    return digits, name


def require_ksef_token(token: str) -> str:
    """The token to encrypt. Shorter than four characters is refused. Nothing here stores it."""
    cleaned = token.strip()
    if len(cleaned) < 4:
        raise Invalid("KSeF token is too short")
    return cleaned


def client_document(name: str, content_text: str) -> tuple[str, str]:
    """The document name and text to store. Text over 1 MB is refused."""
    cleaned = name.strip()
    if not cleaned:
        raise Invalid("Document name is empty")
    size = len(content_text.encode())
    if size > DOCUMENT_BYTE_LIMIT:
        raise Invalid(f"Document is {size} bytes. The limit is {DOCUMENT_BYTE_LIMIT} bytes")
    return cleaned, content_text
