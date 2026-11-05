"""Encrypt secrets before they go into the store. Decrypt only outside a UnitOfWork."""

from cryptography.fernet import Fernet, InvalidToken

from grok_invoices.domain.errors import Invalid
from grok_invoices.settings import get_settings


def _fernet() -> Fernet:
    key = get_settings().secret_encryption_key
    if not key:
        raise Invalid("Secret encryption is not configured")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as error:
        raise Invalid("Secret encryption key is invalid") from error


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError) as error:
        raise Invalid("Stored KSeF token could not be decrypted") from error
