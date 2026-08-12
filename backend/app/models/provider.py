"""Who performs the work, as opposed to what the work is.

The distinction this file exists to make: a **service** is what a customer needs
(a leak found and fixed), and a **provider** is a business that does it (ABC
Plumbing). They are separate because the relationship between them is many to
many in both directions, and because a price, a duration and an availability
belong to a particular business rather than to the idea of a service.

Until now `services` was a renamed product table and there was nobody to perform
anything. That worked for matching and cannot work for booking: an appointment
has to be with somebody.

Deliberately not modelled around plumbing. A provider carries categories and a
list of services, and nothing here knows or cares which trade it is.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, Numeric,
    String, Text, Time, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Provider(Base):
    """A business that performs services."""

    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, autoincrement=True)

    business_name = Column(String(200), nullable=False)
    contact_name  = Column(String(160))
    email         = Column(String(255), nullable=False, unique=True)
    phone         = Column(String(40))
    website       = Column(String(400))
    description   = Column(Text)

    address   = Column(Text)
    city      = Column(String(120))
    postcode  = Column(String(20))
    latitude  = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    # How far they will travel. Used to decline politely and early rather than
    # after a customer has chosen a time.
    travel_radius_miles = Column(Integer, default=15)

    # Applications are held rather than published. Anybody can apply; the office
    # decides who customers can actually book. See the registration endpoint.
    status = Column(
        Enum("pending", "active", "suspended", "rejected"),
        nullable=False,
        default="pending",
    )
    # Whether this business wants to confirm each booking itself, or lets the
    # diary take them automatically. Both are real business models and the
    # platform should not impose one.
    requires_approval = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    services     = relationship("ProviderService", back_populates="provider",
                                cascade="all, delete-orphan")
    availability = relationship("ProviderAvailability", back_populates="provider",
                                cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_provider_status", "status"),
    )


class ProviderService(Base):
    """One business offering one service, on its own terms.

    The join carries a price and a duration because those belong to the business
    rather than to the service: one firm charges 89 for a drain and takes an
    hour, another charges 120 and takes ninety minutes. The service row keeps a
    guide price for matching and for showing a range before a provider is
    chosen; this row is what a booking is actually made against.
    """

    __tablename__ = "provider_services"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"),
                         nullable=False)
    service_id  = Column(Integer, ForeignKey("services.id"), nullable=False)

    price            = Column(Numeric(10, 2))
    duration_minutes = Column(Integer)
    #: Their own words for it, where the generic description is not theirs.
    notes  = Column(Text)
    active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, server_default=func.now())

    provider = relationship("Provider", back_populates="services")

    __table_args__ = (
        # A business offers a service once. Twice is a data error, and it would
        # show the same firm twice in a list of who can help.
        UniqueConstraint("provider_id", "service_id", name="uq_provider_service"),
        Index("ix_provider_service_service", "service_id", "active"),
    )


class ProviderAvailability(Base):
    """When a business works.

    One row per weekday it opens. Absence of a row means closed that day, which
    is why Sunday is usually missing rather than present and empty.

    The diary computes free slots from these hours with existing appointments
    and the length of the job taken out, so this is the only thing a provider
    has to maintain for booking to work.
    """

    __tablename__ = "provider_availability"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"),
                         nullable=False)

    # 0 is Monday, matching Python's weekday().
    weekday    = Column(Integer, nullable=False)
    opens_at   = Column(Time, nullable=False)
    closes_at  = Column(Time, nullable=False)
    #: Emergency work outside these hours, charged differently by the business.
    out_of_hours = Column(Boolean, nullable=False, default=False)

    provider = relationship("Provider", back_populates="availability")

    __table_args__ = (
        UniqueConstraint("provider_id", "weekday", "opens_at",
                         name="uq_provider_weekday"),
    )
