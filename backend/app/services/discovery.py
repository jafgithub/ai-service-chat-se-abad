"""Who can do this, and in what order to show them.

The matching engine answers "what is this person asking for" and stops there.
This answers the next question: given that service, which businesses offer it,
what do they each charge, how long do they each take, and when could they come.

Ordering is a business rule, not a technical one, so it is a setting. The
default is soonest availability then price, because somebody with water coming
through a ceiling cares first about when and only then about how much. A
platform selling gutter cleaning might well want the opposite, and that should
not need a deployment.

Distance and rating are named and deliberately not implemented: there is no
customer location on a search and no ratings exist yet. They fall back to the
default rather than silently ordering by nothing.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.provider import Provider, ProviderService
from app.models.service import Service
from app.services.calendly.local_provider import LocalCalendar

logger = logging.getLogger("booking")

#: Ranking a long list means computing a diary for each one, so the list is
#: capped. Nobody reads past the first handful of tradespeople anyway.
_MAX_RANKED = 12


@dataclass
class Offering:
    """One provider's version of one service: their price, their time, their
    next free slot."""

    provider: Provider
    provider_service: ProviderService
    service: Service
    next_available: datetime | None

    @property
    def price(self) -> float:
        """The provider's price, falling back to the service's guide price.

        The join is authoritative. The service row carries a guide figure for
        matching and for showing a range before anybody is chosen, and it must
        never override what a business actually charges.
        """
        if self.provider_service.price is not None:
            return float(self.provider_service.price)
        return float(self.service.price or 0)

    @property
    def duration_minutes(self) -> int:
        """Likewise: the business decides how long its own job takes."""
        if self.provider_service.duration_minutes:
            return int(self.provider_service.duration_minutes)
        return int(self.service.duration_minutes or 60)


def offerings_for_service(db: Session, service: Service,
                          days_ahead: int | None = None,
                          with_availability: bool = True) -> list[Offering]:
    """Every active provider offering this service, ranked.

    Only `active` providers appear. A pending application can fill in its
    profile and its hours, and is invisible to customers until the office
    approves it.
    """
    rows = (
        db.query(ProviderService, Provider)
        .join(Provider, Provider.id == ProviderService.provider_id)
        .filter(
            ProviderService.service_id == service.id,
            ProviderService.active.is_(True),
            Provider.status == "active",
        )
        .limit(_MAX_RANKED)
        .all()
    )

    horizon = days_ahead or settings.BOOKING_DAYS_AHEAD
    offerings: list[Offering] = []
    for provider_service, provider in rows:
        offering = Offering(
            provider=provider,
            provider_service=provider_service,
            service=service,
            next_available=None,
        )
        if with_availability:
            diary = LocalCalendar(db, provider.id)
            try:
                offering.next_available = diary.next_free(
                    service.id, offering.duration_minutes, days_ahead=horizon
                )
            except Exception as exc:  # noqa: BLE001
                # A provider whose diary cannot be read is still worth showing;
                # they sort last and show no time. Logged with the exception
                # text, not just its class: the first version said only
                # "TypeError" and hid a driver quirk that made every provider
                # look fully booked.
                logger.warning(
                    f"[BOOKING] diary unreadable for provider {provider.id} "
                    f"({provider.business_name}): {type(exc).__name__}: {exc}"
                )
        offerings.append(offering)

    return rank(offerings)


def rank(offerings: list[Offering], strategy: str | None = None) -> list[Offering]:
    """Order the list. `PROVIDER_RANKING` decides how."""
    choice = (strategy or settings.PROVIDER_RANKING or "soonest").strip().lower()

    #: A provider with no free time in the horizon sorts after everyone who has
    #: some, rather than being dropped: "no times this fortnight" is useful.
    far_future = datetime.max

    if choice == "price":
        return sorted(offerings, key=lambda o: (o.price, o.next_available or far_future))

    if choice in ("distance", "rating"):
        # Named so the setting is honest about what exists. Neither has the data
        # behind it yet, so ordering by nothing would be worse than saying so.
        logger.info(f"[BOOKING] ranking '{choice}' has no data yet; using soonest")
        choice = "soonest"

    # Soonest, then cheapest among those who can come at the same time.
    return sorted(offerings, key=lambda o: (o.next_available or far_future, o.price))
