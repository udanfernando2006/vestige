import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SettingsCipher:
    """AES-256-GCM for the two secret settings fields. Nonce is random per
    encrypt() call and stored alongside the ciphertext — never reused, which
    is the one hard requirement GCM has."""

    def __init__(self, key_b64: str):
        if not key_b64:
            raise ValueError("SettingsCipher requires a non-empty key")
        key = base64.urlsafe_b64decode(key_b64)
        if len(key) != 32:
            raise ValueError("SETTINGS_ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256)")
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ct).decode("ascii")

    def decrypt(self, token: str) -> str:
        raw = base64.urlsafe_b64decode(token)
        nonce, ct = raw[:12], raw[12:]
        return self._aesgcm.decrypt(nonce, ct, None).decode("utf-8")


def build_cipher_from_env() -> "SettingsCipher | None":
    """Every entry point that needs a DBWriter (api_server.py, discover_selectors.py,
    main.py) calls this the same way, so there's one place deciding how the
    cipher gets built. Returns None if no key is configured yet — secret-setting
    reads/writes then fail loudly at the point of use, not at process startup,
    so a fresh deploy that hasn't touched LLM settings yet isn't forced to set
    this up before anything else works."""
    key = os.environ.get("SETTINGS_ENCRYPTION_KEY")
    return SettingsCipher(key) if key else None