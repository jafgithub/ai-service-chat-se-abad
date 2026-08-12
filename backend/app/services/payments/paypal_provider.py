"""PayPal, via the Orders v2 REST API.

Written against httpx, which is already a dependency, rather than pulling in
PayPal's SDK for the three calls we make: get a token, create an order, capture
it. The shopper is redirected to PayPal's approval page, which is the same shape
as the Stripe flow and works with a static frontend.

This is also what brings Venmo: it appears as a funding source on PayPal's page
for US buyers, with no extra integration.
"""

import base64
import json
import logging

import httpx

from app.core.config import settings
from app.services.payments.base import CheckoutSession, PaymentError, PaymentEvent

logger = logging.getLogger("payments")

_STATUS_BY_EVENT = {
    "CHECKOUT.ORDER.APPROVED":     "approved",   # needs capturing, see below
    "PAYMENT.CAPTURE.COMPLETED":   "paid",
    "PAYMENT.CAPTURE.DENIED":      "failed",
    "PAYMENT.CAPTURE.DECLINED":    "failed",
    "CHECKOUT.ORDER.VOIDED":       "cancelled",
}


class PayPalProvider:
    name = "paypal"

    def is_configured(self) -> bool:
        return bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_SECRET)

    def _base(self) -> str:
        return settings.PAYPAL_BASE_URL.rstrip("/")

    def _token(self) -> str:
        """OAuth token. Fetched per call: they last hours, but the call is cheap
        and caching one would need invalidation we do not have anywhere else."""
        creds = f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_SECRET}".encode()
        try:
            resp = httpx.post(
                f"{self._base()}/v1/oauth2/token",
                headers={"Authorization": f"Basic {base64.b64encode(creds).decode()}"},
                data={"grant_type": "client_credentials"},
                timeout=20,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"[PAY] paypal token failed: {type(exc).__name__}")
            raise PaymentError("Could not authenticate with PayPal.") from exc
        return resp.json()["access_token"]

    def create_checkout(
        self, *, order_id: int, amount: float, currency: str,
        description: str, success_url: str, cancel_url: str,
    ) -> CheckoutSession:
        if not self.is_configured():
            raise PaymentError("PayPal is not configured on the server.")

        try:
            resp = httpx.post(
                f"{self._base()}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {self._token()}",
                    "Content-Type": "application/json",
                },
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        # Comes back on the webhook so we can find our order.
                        "custom_id": str(order_id),
                        "description": description[:127],   # PayPal's limit
                        "amount": {
                            "currency_code": currency.upper(),
                            "value": f"{amount:.2f}",
                        },
                    }],
                    "payment_source": {
                        "paypal": {
                            "experience_context": {
                                "return_url": success_url,
                                "cancel_url": cancel_url,
                                "user_action": "PAY_NOW",
                            }
                        }
                    },
                },
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            body = getattr(getattr(exc, "response", None), "text", "")[:300]
            logger.warning(f"[PAY] paypal create failed: {type(exc).__name__} {body}")
            raise PaymentError("Could not start the PayPal checkout.") from exc

        data = resp.json()
        approve = next(
            (l["href"] for l in data.get("links", []) if l.get("rel") in ("approve", "payer-action")),
            None,
        )
        if not approve:
            raise PaymentError("PayPal did not return an approval link.")

        logger.info(f"[PAY] paypal order {data['id']} for order {order_id}, {currency} {amount}")
        return CheckoutSession(url=approve, provider_ref=data["id"])

    def capture(self, provider_ref: str) -> bool:
        """Take the money for an approved order. Returns True when completed.

        PayPal splits approval from capture: the shopper approving on PayPal's
        page does not move any money. Already-captured orders return 422 with
        ORDER_ALREADY_CAPTURED, which is a success from our point of view.
        """
        try:
            resp = httpx.post(
                f"{self._base()}/v2/checkout/orders/{provider_ref}/capture",
                headers={
                    "Authorization": f"Bearer {self._token()}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
        except httpx.HTTPError as exc:
            logger.warning(f"[PAY] paypal capture failed: {type(exc).__name__}")
            raise PaymentError("Could not capture the PayPal payment.") from exc

        if resp.status_code == 422 and "ORDER_ALREADY_CAPTURED" in resp.text:
            logger.info(f"[PAY] paypal {provider_ref} was already captured")
            return True
        if resp.status_code >= 400:
            logger.warning(f"[PAY] paypal capture {resp.status_code}: {resp.text[:200]}")
            return False
        return resp.json().get("status") == "COMPLETED"

    def parse_webhook(self, raw_body: bytes, headers: dict) -> PaymentEvent:
        if not self.is_configured():
            raise PaymentError("PayPal is not configured on the server.")
        if not settings.PAYPAL_WEBHOOK_ID:
            raise PaymentError("PAYPAL_WEBHOOK_ID is not set, so webhooks cannot be verified.")

        # PayPal verifies by calling them back with the headers and the body,
        # rather than by us checking an HMAC locally as Stripe does.
        try:
            resp = httpx.post(
                f"{self._base()}/v1/notifications/verify-webhook-signature",
                headers={
                    "Authorization": f"Bearer {self._token()}",
                    "Content-Type": "application/json",
                },
                json={
                    "auth_algo":         headers.get("paypal-auth-algo", ""),
                    "cert_url":          headers.get("paypal-cert-url", ""),
                    "transmission_id":   headers.get("paypal-transmission-id", ""),
                    "transmission_sig":  headers.get("paypal-transmission-sig", ""),
                    "transmission_time": headers.get("paypal-transmission-time", ""),
                    "webhook_id":        settings.PAYPAL_WEBHOOK_ID,
                    # Their API wants the parsed event here, not the raw bytes.
                    "webhook_event":     json.loads(raw_body),
                },
                timeout=20,
            )
            resp.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(f"[PAY] paypal verify failed: {type(exc).__name__}")
            raise PaymentError("Could not verify the PayPal signature.") from exc

        if resp.json().get("verification_status") != "SUCCESS":
            logger.warning("[PAY] paypal webhook signature did not verify")
            raise PaymentError("Invalid PayPal signature.")

        event = json.loads(raw_body)
        resource = event.get("resource", {})
        # The id we need differs by event: capture events carry the order id in
        # supplementary_data, order events carry it directly.
        provider_ref = (
            resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
            or resource.get("id", "")
        )
        return PaymentEvent(
            event_id=event.get("id", ""),
            provider_ref=provider_ref,
            status=_STATUS_BY_EVENT.get(event.get("event_type", ""), "ignored"),
            raw_type=event.get("event_type", ""),
        )
