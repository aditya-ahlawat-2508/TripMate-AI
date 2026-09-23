"""Razorpay subscriptions (docs/blueprint.md §08 Payments). Test mode
only — RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET are test keys
(rzp_test_...). Order creation is verified live against the real
Razorpay sandbox API (docs/progress.md); the webhook signature check is
unit-tested but not exercised against a real webhook delivery, since
that needs a public URL Razorpay can reach.
"""

import os

import razorpay

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# blueprint §03 Monetization: Pro is ₹199-299/mo or ₹1,499/yr — a starting
# hypothesis to validate, not a researched price. ₹249/mo picked as the
# midpoint for this first cut.
PRO_PLAN_AMOUNT_MINOR = 24900
PRO_PLAN_CURRENCY = "INR"

_client: razorpay.Client | None = None


def get_client() -> razorpay.Client:
    global _client
    if _client is None:
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            raise RuntimeError("Razorpay is not configured (RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET)")
        _client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    return _client


def create_pro_order(owner_id: str) -> dict:
    """One Razorpay "order" per checkout attempt — the frontend opens
    Razorpay's checkout with this order_id, and the webhook (below)
    confirms payment and activates the subscription. Nothing is charged
    by creating an order; it's just a pending-payment record."""

    client = get_client()
    return client.order.create(
        {
            "amount": PRO_PLAN_AMOUNT_MINOR,
            "currency": PRO_PLAN_CURRENCY,
            "notes": {"owner_id": owner_id, "plan": "pro"},
        }
    )


def verify_webhook_signature(body: bytes, signature: str, webhook_secret: str) -> bool:
    """Razorpay signs webhook payloads with HMAC-SHA256 over the raw
    request body, keyed by a webhook secret set in the Razorpay dashboard
    (separate from the API key/secret pair) — this must match exactly or
    the event is not trusted. Uses the SDK's own verifier so this stays
    correct if Razorpay ever changes the scheme."""

    client = razorpay.Client(auth=(RAZORPAY_KEY_ID or "", RAZORPAY_KEY_SECRET or ""))
    try:
        client.utility.verify_webhook_signature(body.decode(), signature, webhook_secret)
        return True
    except razorpay.errors.SignatureVerificationError:
        return False
