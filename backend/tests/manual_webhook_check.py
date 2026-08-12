"""Drive the Stripe webhook endpoint with a correctly signed payload.

Not a unit test: it talks to a running server and a real database, so it lives
outside tests/ conventions and is invoked by hand.

    .venv/bin/python tests/manual_webhook_check.py --order 51 --ref cs_test_...

It proves the three things that matter and cannot be checked by reading code:

  1. a payload signed with the real webhook secret is accepted
  2. accepting it confirms the order exactly once
  3. replaying the identical delivery changes nothing

It also sends a deliberately mis-signed payload, which must be rejected with a
400. That one is the important negative: the webhook endpoint is public, so
anything that skipped signature checking would let a stranger mark orders paid.
"""

import argparse
import hashlib
import hmac
import json
import sys
import time

import httpx

sys.path.insert(0, ".")
from app.core.config import settings  # noqa: E402


def signed_headers(payload: str, secret: str, timestamp: int) -> dict:
    """Reproduce Stripe's scheme: HMAC-SHA256 over "<timestamp>.<payload>"."""
    signed = f"{timestamp}.{payload}".encode()
    mac = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return {
        "Stripe-Signature": f"t={timestamp},v1={mac}",
        "Content-Type": "application/json",
    }


def event(order_id: int, provider_ref: str, event_id: str, kind: str) -> str:
    return json.dumps({
        "id": event_id,
        "object": "event",
        "type": kind,
        "data": {"object": {
            "id": provider_ref,
            "object": "checkout.session",
            "client_reference_id": str(order_id),
            "payment_status": "paid",
        }},
    })


def post(url: str, body: str, headers: dict) -> tuple[int, str]:
    r = httpx.post(url, content=body.encode(), headers=headers, timeout=30)
    return r.status_code, r.text[:200]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--order", type=int, required=True)
    ap.add_argument("--ref", required=True, help="the Stripe session id from /checkout")
    ap.add_argument("--url", default="http://127.0.0.1:8000/api/v1/payments/webhook/stripe")
    args = ap.parse_args()

    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret:
        sys.exit("STRIPE_WEBHOOK_SECRET is not set")

    ts = int(time.time())
    event_id = f"evt_manualcheck_{ts}"
    body = event(args.order, args.ref, event_id, "checkout.session.completed")

    print("1. correctly signed delivery")
    code, text = post(args.url, body, signed_headers(body, secret, ts))
    print(f"   HTTP {code}  {text}")

    print("2. identical delivery replayed")
    code, text = post(args.url, body, signed_headers(body, secret, ts))
    print(f"   HTTP {code}  {text}")

    print("3. forged signature, must be rejected")
    bad = dict(signed_headers(body, "whsec_not_the_real_secret", ts))
    code, text = post(args.url, body, bad)
    print(f"   HTTP {code}  {text}")
    if code != 400:
        sys.exit(f"SECURITY FAILURE: a bad signature returned {code}, expected 400")

    print("\nlooks right if: 1 handled, 2 duplicate, 3 rejected with 400")


if __name__ == "__main__":
    main()
