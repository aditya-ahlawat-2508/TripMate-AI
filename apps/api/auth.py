"""Clerk JWT verification (docs/blueprint.md §08 Auth). No Clerk Python
SDK dependency — just PyJWT against Clerk's public JWKS, which is all
verifying a session token actually needs.

CLERK_ISSUER is the Clerk Frontend API host encoded in the publishable
key (e.g. a pk_test_... key's base64 payload decodes to
"your-app.clerk.accounts.dev$" — CLERK_ISSUER is that domain, https://).
"""

import os

import jwt
from fastapi import HTTPException, Request

CLERK_ISSUER = os.getenv("CLERK_ISSUER")

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not CLERK_ISSUER:
            raise RuntimeError("CLERK_ISSUER is not configured")
        _jwks_client = jwt.PyJWKClient(f"{CLERK_ISSUER}/.well-known/jwks.json")
    return _jwks_client


def verify_token(token: str) -> dict:
    """Raises on any invalid/expired/malformed token — callers decide
    whether that's a hard failure (require_user_id) or just "not signed
    in" (get_current_user_id)."""

    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=CLERK_ISSUER,
        options={"verify_aud": False},
    )


def _extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer ") :]


async def get_current_user_id(request: Request) -> str | None:
    """Optional auth: returns the Clerk user ID (JWT 'sub' claim) if a
    valid session token was sent, None otherwise — never raises. Use this
    where signing in is encouraged but not required (e.g. /api/plan,
    which still works anonymously)."""

    token = _extract_bearer_token(request)
    if not token or not CLERK_ISSUER:
        return None
    try:
        return verify_token(token).get("sub")
    except Exception:
        return None


async def require_user_id(request: Request) -> str:
    """Hard auth: 401s if there's no valid session. Use this for routes
    that only make sense for a signed-in user, e.g. GET /api/trips."""

    user_id = await get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return user_id
