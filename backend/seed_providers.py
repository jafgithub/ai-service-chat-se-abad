"""Realistic providers, so discovery and the diary have something to work on.

Data only. Nothing in the application knows these businesses exist, and none of
them is special: they are rows, and deleting them leaves a working system with
an empty marketplace.

Two things are set up on purpose, because they are what the ranking and the
booking rules have to be tested against:

* **The same service offered by several firms at different prices and
  durations.** A drain is 89 and an hour with one, 120 and ninety minutes with
  another. Ranking is meaningless without it, and so is the rule that a booking
  uses the provider's figures rather than the service's guide.
* **Different working weeks.** One works Saturdays, one starts at seven, one
  keeps short Fridays. Availability that never differs proves nothing.

    python seed_providers.py            # add what is missing
    python seed_providers.py --reset    # start again
"""

import sys
from datetime import time

from sqlalchemy import text

from app.db.database import SessionLocal
from app.models.provider import Provider, ProviderAvailability, ProviderService
from app.models.service import Service

# business, contact, email, phone, website, city, description, requires_approval
PROVIDERS = [
    ("Riverside Plumbing & Heating", "Alan Brook", "office@riversideplumbing.example",
     "01234 567890", "https://riversideplumbing.example", "Riverside",
     "Family run since 2004. Gas Safe registered, emergency call outs, no call out fee.",
     False),
    ("Quickfix Drains", "Dee Patel", "hello@quickfixdrains.example",
     "01234 111222", "https://quickfixdrains.example", "Riverside",
     "Drains and blockages only. Usually same day, often within two hours.",
     False),
    ("Brightspark Electrical", "Nina Okafor", "bookings@brightspark.example",
     "01234 333444", "https://brightspark.example", "Riverside",
     "Domestic electricians. Fuse boards, rewires, sockets and fault finding.",
     False),
    ("Meadow Vets", "Dr Sam Reid", "reception@meadowvets.example",
     "01234 555666", "https://meadowvets.example", "Meadowfield",
     "Small animal practice. Consultations, vaccinations and microchipping.",
     True),
    ("Sparkle Home Cleaning", "Marta Nowak", "book@sparklecleaning.example",
     "01234 777888", "https://sparklecleaning.example", "Riverside",
     "Regular and one off cleans, end of tenancy, carpets and upholstery.",
     False),
    ("Greenway Garden Care", "Tom Ellis", "tom@greenwaygardens.example",
     "01234 999000", None, "Meadowfield",
     "Grass, hedges, clearances and seasonal tidy ups.",
     False),
    ("Fastlane Motors", "Ryan Cole", "service@fastlanemotors.example",
     "01234 222333", "https://fastlanemotors.example", "Riverside",
     "Servicing, tyres, diagnostics and a mobile mechanic for breakdowns.",
     False),
    ("Northside Community Centre", "Grace Adeyemi", "hall@northsidecentre.example",
     "01234 444555", "https://northsidecentre.example", "Northside",
     "Rooms and halls to hire, classes, and free advice appointments.",
     True),
]

# provider email -> weekday -> (opens, closes). Missing day means closed.
HOURS = {
    "office@riversideplumbing.example": {d: (time(8, 0), time(17, 0)) for d in range(5)},
    # Starts early, works Saturday mornings.
    "hello@quickfixdrains.example": {
        **{d: (time(7, 0), time(18, 0)) for d in range(5)},
        5: (time(8, 0), time(12, 0)),
    },
    "bookings@brightspark.example": {d: (time(8, 30), time(16, 30)) for d in range(5)},
    # A vet's day, with a closed lunchtime expressed as two periods.
    "reception@meadowvets.example": {d: (time(9, 0), time(18, 0)) for d in range(5)},
    "book@sparklecleaning.example": {d: (time(9, 0), time(15, 0)) for d in range(5)},
    # Short Friday.
    "tom@greenwaygardens.example": {
        **{d: (time(8, 0), time(16, 0)) for d in range(4)},
        4: (time(8, 0), time(13, 0)),
    },
    "service@fastlanemotors.example": {d: (time(8, 0), time(17, 30)) for d in range(5)},
    "hall@northsidecentre.example": {d: (time(9, 0), time(21, 0)) for d in range(6)},
}

# provider email -> [(service name fragment, price, minutes)]
OFFERS = {
    "office@riversideplumbing.example": [
        ("Blocked drain cleared", 89, 60),
        ("Leak found and fixed", 95, 90),
        ("Dripping tap repaired", 65, 45),
        ("Boiler repaired", 120, 120),
        ("Boiler serviced", 90, 60),
        ("Radiator repaired", 85, 90),
    ],
    # Same drain, dearer and slower, because they bring a jetter.
    "hello@quickfixdrains.example": [
        ("Blocked drain cleared", 120, 90),
        ("Blocked toilet cleared", 95, 60),
        ("Leak found and fixed", 110, 60),
    ],
    "bookings@brightspark.example": [
        ("Electrician call out", 95, 90),
        ("Appliance repaired", 75, 60),
    ],
    "reception@meadowvets.example": [
        ("Vet consultation", 55, 30),
        ("Vaccinations and boosters", 45, 20),
        ("Microchipping", 25, 15),
    ],
    "book@sparklecleaning.example": [
        ("House clean", 60, 120),
        ("Carpet or upholstery clean", 80, 120),
        ("Window cleaning", 25, 45),
    ],
    "tom@greenwaygardens.example": [
        ("Garden maintenance", 55, 120),
        ("Waste or rubbish removal", 90, 90),
        # Undercuts the cleaning firm on windows, and is quicker.
        ("Window cleaning", 20, 30),
    ],
    "service@fastlanemotors.example": [
        ("Car service", 140, 180),
        ("Mobile mechanic call out", 70, 60),
        ("Tyres fitted", 60, 45),
        ("Vehicle inspection", 45, 60),
    ],
    "hall@northsidecentre.example": [
        ("Community hall booking", 35, 180),
        ("Class or workshop place", 12, 90),
        ("Advice appointment", 0, 45),
    ],
}


def main() -> None:
    db = SessionLocal()
    reset = "--reset" in sys.argv
    try:
        if reset:
            # Only the seeded businesses, found by their example.com addresses,
            # so a real provider registered through the form is never touched.
            db.execute(text(
                "DELETE FROM providers WHERE email LIKE '%@%.example'"
            ))
            db.commit()
            print("removed seeded providers")

        by_email: dict[str, Provider] = {}
        for (name, contact, email, phone, website, city, description,
             approval) in PROVIDERS:
            provider = db.query(Provider).filter(Provider.email == email).first()
            if provider is None:
                provider = Provider(email=email)
                db.add(provider)
            provider.business_name = name
            provider.contact_name = contact
            provider.phone = phone
            provider.website = website
            provider.city = city
            provider.description = description
            provider.requires_approval = approval
            # Seeded businesses are approved, because an empty marketplace
            # cannot be tested. A real application still starts pending.
            provider.status = "active"
            by_email[email] = provider
        db.commit()

        services = {s.name: s for s in db.query(Service).all()}

        def find(fragment: str) -> Service | None:
            for name, service in services.items():
                if fragment.lower() in (name or "").lower():
                    return service
            return None

        offers = 0
        missing: list[str] = []
        for email, rows in OFFERS.items():
            provider = by_email[email]
            db.refresh(provider)
            for fragment, price, minutes in rows:
                service = find(fragment)
                if service is None:
                    missing.append(fragment)
                    continue
                row = (
                    db.query(ProviderService)
                    .filter(ProviderService.provider_id == provider.id,
                            ProviderService.service_id == service.id)
                    .first()
                )
                if row is None:
                    row = ProviderService(provider_id=provider.id,
                                          service_id=service.id)
                    db.add(row)
                row.price = price
                row.duration_minutes = minutes
                row.active = True
                offers += 1
        db.commit()

        hours = 0
        for email, week in HOURS.items():
            provider = by_email[email]
            for weekday, (opens, closes) in week.items():
                row = (
                    db.query(ProviderAvailability)
                    .filter(ProviderAvailability.provider_id == provider.id,
                            ProviderAvailability.weekday == weekday)
                    .first()
                )
                if row is None:
                    row = ProviderAvailability(provider_id=provider.id,
                                               weekday=weekday)
                    db.add(row)
                row.opens_at = opens
                row.closes_at = closes
                hours += 1
        db.commit()

        print(f"{len(PROVIDERS)} providers, {offers} service offers, {hours} working days")
        if missing:
            print(f"  no matching service for: {sorted(set(missing))}")

        shared = db.execute(text("""
            SELECT s.name, COUNT(*) AS providers,
                   MIN(ps.price) AS cheapest, MAX(ps.price) AS dearest
            FROM provider_services ps
            JOIN services s ON s.id = ps.service_id
            GROUP BY s.name HAVING COUNT(*) > 1
            ORDER BY providers DESC
        """)).fetchall()
        print("\noffered by more than one provider:")
        for name, count, low, high in shared:
            print(f"  {name:32} {count} providers, {low} to {high}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
