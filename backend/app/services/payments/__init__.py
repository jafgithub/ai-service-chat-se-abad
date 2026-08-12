"""Provider registry.

`get(name)` is the only way the API reaches a provider, so adding a third one
means writing a module and adding a line here.
"""

from app.services.payments.base import (
    CheckoutSession, PaymentError, PaymentEvent, PaymentProvider,
)
from app.services.payments.paypal_provider import PayPalProvider
from app.services.payments.stripe_provider import StripeProvider

_PROVIDERS: dict[str, PaymentProvider] = {
    "stripe": StripeProvider(),
    "paypal": PayPalProvider(),
}


def get(name: str) -> PaymentProvider:
    provider = _PROVIDERS.get((name or "").lower())
    if provider is None:
        raise PaymentError(f"Unknown payment provider '{name}'.")
    return provider


def available() -> list[str]:
    """Providers whose keys are actually set, so the checkout only offers what works."""
    return [name for name, p in _PROVIDERS.items() if p.is_configured()]


__all__ = [
    "get", "available",
    "CheckoutSession", "PaymentError", "PaymentEvent", "PaymentProvider",
]
