import pytest
from cryptography.fernet import Fernet

from src.core.config import Settings


def test_malformed_encryption_key_is_refused_at_startup():
    # A hex key, as `openssl rand -hex 32` would give, is not a Fernet key
    with pytest.raises(ValueError, match="not a valid Fernet key"):
        Settings(DOCUMENT_ENCRYPTION_KEY="ab" * 32)
    assert Settings(DOCUMENT_ENCRYPTION_KEY=Fernet.generate_key().decode()).DOCUMENT_ENCRYPTION_KEY
