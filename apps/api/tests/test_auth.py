import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

import auth


class FakeRequest:
    def __init__(self, authorization: str | None = None):
        self.headers = {"Authorization": authorization} if authorization else {}


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def signed_token(rsa_keypair):
    private_key, _ = rsa_keypair
    payload = {"sub": "user_abc123", "iss": "https://test.clerk.accounts.dev", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key"})


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


@pytest.fixture(autouse=True)
def patch_issuer(monkeypatch):
    monkeypatch.setattr(auth, "CLERK_ISSUER", "https://test.clerk.accounts.dev")
    auth._jwks_client = None
    yield
    auth._jwks_client = None


def test_verify_token_accepts_valid_signature(monkeypatch, rsa_keypair, signed_token):
    _, public_key = rsa_keypair

    class FakeJWKSClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey(public_key)

    monkeypatch.setattr(auth, "_get_jwks_client", lambda: FakeJWKSClient())

    payload = auth.verify_token(signed_token)
    assert payload["sub"] == "user_abc123"


def test_verify_token_rejects_wrong_key(monkeypatch, rsa_keypair, signed_token):
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class FakeJWKSClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey(other_private_key.public_key())

    monkeypatch.setattr(auth, "_get_jwks_client", lambda: FakeJWKSClient())

    with pytest.raises(jwt.InvalidSignatureError):
        auth.verify_token(signed_token)


def test_verify_token_rejects_wrong_issuer(monkeypatch, rsa_keypair):
    private_key, public_key = rsa_keypair
    payload = {"sub": "user_abc123", "iss": "https://someone-else.clerk.accounts.dev", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, private_key, algorithm="RS256")

    class FakeJWKSClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey(public_key)

    monkeypatch.setattr(auth, "_get_jwks_client", lambda: FakeJWKSClient())

    with pytest.raises(jwt.InvalidIssuerError):
        auth.verify_token(token)


@pytest.mark.asyncio
async def test_get_current_user_id_no_header_returns_none():
    assert await auth.get_current_user_id(FakeRequest()) is None


@pytest.mark.asyncio
async def test_get_current_user_id_malformed_header_returns_none():
    assert await auth.get_current_user_id(FakeRequest("NotBearer xyz")) is None


@pytest.mark.asyncio
async def test_get_current_user_id_invalid_token_returns_none(monkeypatch):
    monkeypatch.setattr(auth, "verify_token", lambda token: (_ for _ in ()).throw(jwt.InvalidTokenError()))
    assert await auth.get_current_user_id(FakeRequest("Bearer garbage")) is None


@pytest.mark.asyncio
async def test_get_current_user_id_valid_token_returns_sub(monkeypatch):
    monkeypatch.setattr(auth, "verify_token", lambda token: {"sub": "user_xyz"})
    assert await auth.get_current_user_id(FakeRequest("Bearer valid")) == "user_xyz"


@pytest.mark.asyncio
async def test_require_user_id_raises_401_when_not_signed_in():
    with pytest.raises(HTTPException) as exc_info:
        await auth.require_user_id(FakeRequest())
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_user_id_returns_id_when_signed_in(monkeypatch):
    monkeypatch.setattr(auth, "verify_token", lambda token: {"sub": "user_xyz"})
    assert await auth.require_user_id(FakeRequest("Bearer valid")) == "user_xyz"
