class DomainError(Exception):
    """A rule of the platform refused the request. Entrypoints decide how to report it."""


class NotFound(DomainError):
    pass


class Conflict(DomainError):
    """The request is valid but not allowed in the current state."""


class Invalid(DomainError):
    """The request can never be valid."""


class KsefUnavailable(DomainError):
    """KSeF could not complete the call. Fixtures remain available as a fallback."""


class LegalSourceUnavailable(DomainError):
    """No usable official legal evidence was acquired. Never implies approval."""
