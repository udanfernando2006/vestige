import pytest
import base64
import secrets
from security.crypto import SettingsCipher


def test_cipher_round_trip():
    """Verifies that plaintext can be securely encrypted and decrypted back accurately."""
    # Generate a cryptographically secure 32-byte key and base64-encode it
    raw_key = secrets.token_bytes(32)
    key_b64 = base64.urlsafe_b64encode(raw_key).decode("ascii")

    cipher = SettingsCipher(key_b64)
    secret_text = "sk-proj-LLMDiscoverySecretKeyToken12345!#$"

    # Encrypt text and confirm it has been altered
    encrypted = cipher.encrypt(secret_text)
    assert encrypted != secret_text
    assert len(encrypted) > 0

    # Decrypt and confirm round-trip fidelity
    decrypted = cipher.decrypt(encrypted)
    assert decrypted == secret_text


def test_cipher_wrong_length_rejection():
    """Verifies that keys which do not decode to exactly 32 bytes throw a ValueError."""
    # Too short (24 bytes)
    short_key = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("ascii")
    with pytest.raises(
        ValueError, match="SETTINGS_ENCRYPTION_KEY must decode to exactly 32 bytes"
    ):
        SettingsCipher(short_key)

    # Too long (40 bytes)
    long_key = base64.urlsafe_b64encode(secrets.token_bytes(40)).decode("ascii")
    with pytest.raises(
        ValueError, match="SETTINGS_ENCRYPTION_KEY must decode to exactly 32 bytes"
    ):
        SettingsCipher(long_key)


def test_cipher_empty_and_null_key_rejection():
    """Verifies that initializing with empty strings or missing configuration throws a clear error."""
    with pytest.raises(ValueError, match="SettingsCipher requires a non-empty key"):
        SettingsCipher("")

    with pytest.raises(ValueError, match="SettingsCipher requires a non-empty key"):
        SettingsCipher(None)
