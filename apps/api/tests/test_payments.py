import hashlib
import hmac

from payments import PRO_PLAN_AMOUNT_MINOR, verify_webhook_signature


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_webhook_signature_accepts_valid_signature():
    body = b'{"event": "payment.captured"}'
    secret = "whsec_test"
    signature = sign(body, secret)

    assert verify_webhook_signature(body, signature, secret) is True


def test_verify_webhook_signature_rejects_wrong_signature():
    body = b'{"event": "payment.captured"}'
    assert verify_webhook_signature(body, "not-a-real-signature", "whsec_test") is False


def test_verify_webhook_signature_rejects_tampered_body():
    secret = "whsec_test"
    signature = sign(b'{"event": "payment.captured", "amount": 100}', secret)
    tampered_body = b'{"event": "payment.captured", "amount": 999999}'

    assert verify_webhook_signature(tampered_body, signature, secret) is False


def test_pro_plan_amount_is_positive():
    assert PRO_PLAN_AMOUNT_MINOR > 0
