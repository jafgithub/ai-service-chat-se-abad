"""Stripe, via hosted Checkout.

Hosted rather than embedded for two reasons. Card details never touch our
frontend, which keeps us out of the harder PCI tiers, and a redirect is the only
thing that works cleanly with a static export: the frontend has no server to
render a payment form on. Cards, Apple Pay and Google Pay all come free with it,
so this one integration covers three of the methods the client asked for.
"""

import logging

import stripe

from app.core.config import settings
from app.services.payments.base import CheckoutSession, PaymentError, PaymentEvent

logger = logging.getLogger("payments")

# Which Stripe events mean what to us. Anything not listed is acknowledged and
# ignored, because Stripe sends far more than we subscribe to and a 400 on an
# unknown type would make it retry forever.
_STATUS_BY_EVENT = {
    "checkout.session.completed":     "paid",
    "checkout.session.async_payment_succeeded": "paid",
    "checkout.session.async_payment_failed":    "failed",
    "checkout.session.expired":       "cancelled",
}


class StripeProvider:
    name = "stripe"

    def is_configured(self) -> bool:
        return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET)

    def create_checkout(
        self, *, order_id: int, amount: float, currency: str,
        description: str, success_url: str, cancel_url: str,
    ) -> CheckoutSession:
        if not self.is_configured():
            raise PaymentError("Stripe is not configured on the server.")

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[{
                    "quantity": 1,
                    "price_data": {
                        "currency": currency.lower(),
                        # Stripe works in the smallest currency unit, so cents.
                        # round() before int() or 10.99 * 100 becomes 1098.
                        "unit_amount": int(round(amount * 100)),
                        "product_data": {"name": description},
                    },
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                # Comes back on the webhook, so we can find our order from an
                # event that otherwise only carries Stripe's own ids.
                client_reference_id=str(order_id),
                metadata={"order_id": str(order_id)},
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as 502
            logger.warning(f"[PAY] stripe checkout failed: {type(exc).__name__}: {exc}")
            raise PaymentError("Could not start the Stripe checkout.") from exc

        logger.info(f"[PAY] stripe session {session.id} for order {order_id}, {currency} {amount}")
        return CheckoutSession(url=session.url, provider_ref=session.id)

    def parse_webhook(self, raw_body: bytes, headers: dict) -> PaymentEvent:
        if not self.is_configured():
            raise PaymentError("Stripe is not configured on the server.")

        signature = headers.get("stripe-signature", "")
        try:
            # Verifies against the raw bytes. Parsing the JSON first and
            # re-serialising would change the payload and fail the check.
            event = stripe.Webhook.construct_event(
                payload=raw_body,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except Exception as exc:  # noqa: BLE001 - bad signature or malformed body
            logger.warning(f"[PAY] stripe webhook rejected: {type(exc).__name__}")
            raise PaymentError("Invalid Stripe signature.") from exc

        obj = event["data"]["object"]
        return PaymentEvent(
            event_id=event["id"],
            provider_ref=obj.get("id", ""),
            status=_STATUS_BY_EVENT.get(event["type"], "ignored"),
            raw_type=event["type"],
        )
