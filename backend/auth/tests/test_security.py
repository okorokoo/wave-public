from datetime import timedelta

import pytest
from jose import jwt

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from config import settings


class TestHashPassword:
    def test_hashed_differs_from_plain(self):
        hashed = hash_password("mysecretpassword")
        assert hashed != "mysecretpassword"

    def test_verify_correct_password(self):
        hashed = hash_password("correcthorsebatterystaple")
        assert verify_password("correcthorsebatterystaple", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_each_hash_is_unique(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        # bcrypt generates a new salt each time
        assert h1 != h2

    def test_verify_both_hashes_accept_same_plain(self):
        password = "shared_password"
        h1 = hash_password(password)
        h2 = hash_password(password)
        assert verify_password(password, h1) is True
        assert verify_password(password, h2) is True


class TestCreateAccessToken:
    def test_token_is_decodable(self):
        token = create_access_token({"sub": "user-123"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "user-123"

    def test_token_contains_exp(self):
        token = create_access_token({"sub": "user-123"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_custom_expires_delta(self):
        from datetime import datetime, timezone
        delta = timedelta(seconds=60)
        token = create_access_token({"sub": "user-abc"}, expires_delta=delta)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload["exp"]
        now = datetime.now(timezone.utc).timestamp()
        assert abs(exp - now - 60) < 5  # within 5 seconds of expected

    def test_extra_claims_preserved(self):
        token = create_access_token({"sub": "u1", "email": "test@example.com", "username": "tester"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["email"] == "test@example.com"
        assert payload["username"] == "tester"

    def test_wrong_key_raises(self):
        from jose import JWTError
        token = create_access_token({"sub": "u1"})
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-key", algorithms=[settings.ALGORITHM])


class TestCreateRefreshToken:
    def test_token_has_refresh_type(self):
        token = create_refresh_token({"sub": "user-123"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["type"] == "refresh"

    def test_token_contains_sub(self):
        token = create_refresh_token({"sub": "user-xyz"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "user-xyz"

    def test_refresh_token_has_longer_expiry_than_access(self):
        from datetime import datetime, timezone
        access = create_access_token({"sub": "u"})
        refresh = create_refresh_token({"sub": "u"})
        access_payload = jwt.decode(access, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        refresh_payload = jwt.decode(refresh, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert refresh_payload["exp"] > access_payload["exp"]
