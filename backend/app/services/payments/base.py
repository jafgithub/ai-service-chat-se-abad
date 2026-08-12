"""What every payment provider has to offer the rest of the app.

Keeping Stripe and PayPal behind one shape means api/payments.py does not care
which is in use, and a third provider is a new file rather than a new branch in
the endpoint.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CheckoutSession:
    """Where to send the shopper, and how to recognise them coming back."""

    url: str            # the provider's hosted page
    provider_ref: str   # the provider's id for this checkout


@dataclass
class PaymentEvent:
    """A webhook, reduced to the only four things the app acts on."""

    event_id: str        # the provider's id for this delivery, for deduplication
    provider_ref: str    # which checkout it refers to
    status: str          # "paid" | "failed" | "cancelled" | "ignored"
    raw_type: str = ""   # the provider's own event name, for logging


class PaymentError(Exception):
    """The provider refused, or could not be reached."""


class PaymentProvider(Protocol):
    name: str

    def is_configured(self) -> bool:
        """False when the keys are missing, so checkout can hide the option."""

    def create_checkout(
        self, *, order_id: int, amount: float, currency: str,
        description: str, success_url: str, cancel_url: str,
    ) -> CheckoutSession:
        ...

    def parse_webhook(self, raw_body: bytes, headers: dict) -> PaymentEvent:
        """Verify the signature and reduce the payload to a PaymentEvent.

        Must raise PaymentError if the signature does not check out. Never trust
        anything in the body before that: the endpoint is public, so an
        unverified payload is a stranger's claim that they paid.
        """
