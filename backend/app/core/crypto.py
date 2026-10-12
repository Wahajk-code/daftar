"""Encryption of single fields at rest (a vendor's bank account number). The key is derived from SECRET_KEY, so
rotating SECRET_KEY means re-encrypting these fields first."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class FieldCipher:
    def __init__(self, secret_key: str) -> None:
        digest = hashlib.sha256(b"daftar-field-encryption:" + secret_key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("the stored value cannot be decrypted with this key") from exc
