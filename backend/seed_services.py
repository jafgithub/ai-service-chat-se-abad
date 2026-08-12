"""A starting service list, and the words customers actually use for each.

The matching engine is the one that searches 25,631 grocery products. It is not
the bottleneck here, and a plumbing firm has tens of services rather than
thousands. What decides whether it works is the vocabulary in `description`.

That is why each description is written the way a customer talks, not the way a
trade catalogue does. Somebody types "water coming through the ceiling". They do
not type "first floor pipework leak investigation". The phrases below are the
whole point of this file, and they are the thing to sit down with the firm and
extend, because they know what people ring up and say.

    python seed_services.py            # add anything missing, change nothing else
    python seed_services.py --reset    # start again
"""

import sys

# A service cannot sell out. The shared code paths inherited from the shop read
# `stock`, and treat zero as unavailable: the search hides the row and the cart
# refuses it. Both were doing exactly that, so "car will not start" found
# nothing and "book the community hall" answered "not enough stock".
#
# A large number rather than a change to those paths, because availability here
# is time and the slot hold is what guards it. This keeps one code path across
# both systems, with the reason written down.
UNLIMITED = 999_999

from app.db.database import SessionLocal, engine, Base
from app.models.service import Service

# name, category, price from, minutes, emergency, what people say
SERVICES = [
    # ── Home & Repairs ───────────────────────────────────────────────────────
    ("Blocked drain cleared", "Home & Repairs", 89, 60, True,
     "Blocked drain, sink not draining, water backing up, gurgling plughole, "
     "outside drain overflowing, kitchen sink blocked with grease"),
    ("Blocked toilet cleared", "Home & Repairs", 79, 45, True,
     "Toilet blocked, will not flush, water rising in the pan, overflowing toilet"),
    ("Dripping tap repaired", "Home & Repairs", 65, 45, False,
     "Dripping tap, leaking tap, tap will not turn off, washer gone, noisy tap"),
    ("Leak found and fixed", "Home & Repairs", 95, 90, True,
     "Water leak, leaking pipe, water coming through the ceiling, damp patch, "
     "puddle under the sink, wet carpet, burst pipe"),
    ("Boiler repaired", "Home & Repairs", 120, 120, True,
     "Boiler not working, no hot water, no heating, boiler locked out, error code, "
     "banging noise, pressure keeps dropping, pilot light out"),
    ("Boiler serviced", "Home & Repairs", 90, 60, False,
     "Boiler service, annual service, landlord gas safety, boiler check"),
    ("Radiator repaired or replaced", "Home & Repairs", 85, 90, False,
     "Radiator cold at the top, radiator not heating, leaking radiator, bleed the radiators"),
    ("Electrician call out", "Home & Repairs", 95, 90, True,
     "No power, tripping fuse box, socket not working, lights flickering, "
     "need a socket fitted, consumer unit, electrical fault"),
    ("Appliance repaired", "Home & Repairs", 80, 90, False,
     "Washing machine not spinning, dishwasher not draining, oven not heating, "
     "fridge not cold, tumble dryer broken"),
    ("Locksmith call out", "Home & Repairs", 90, 60, True,
     "Locked out, lost my keys, broken lock, change the locks, door will not lock"),
    ("Handyperson, half day", "Home & Repairs", 150, 240, False,
     "Odd jobs, shelves put up, flat pack, small repairs, a few little things"),

    # ── Pets & Vets ──────────────────────────────────────────────────────────
    ("Vet consultation", "Pets & Vets", 55, 30, True,
     "My dog is unwell, cat not eating, limping, sick pet, need to see a vet, "
     "my rabbit is poorly, worried about my pet"),
    ("Vaccinations and boosters", "Pets & Vets", 45, 20, False,
     "Vaccinations, boosters, puppy jabs, kitten injections, annual vaccination"),
    ("Microchipping", "Pets & Vets", 25, 15, False,
     "Microchip, chip my dog, chipping a kitten"),
    ("Dog grooming", "Pets & Vets", 45, 90, False,
     "Dog groom, wash and trim, nails clipped, matted coat, puppy first groom"),
    ("Pet sitting or dog walking", "Pets & Vets", 20, 60, False,
     "Dog walker, pet sitting, someone to feed the cat, away for a few days"),

    # ── Health & Wellbeing ───────────────────────────────────────────────────
    ("Dental check up", "Health & Wellbeing", 60, 30, False,
     "Dentist, check up, teeth cleaning, scale and polish, toothache, filling"),
    ("Physiotherapy session", "Health & Wellbeing", 55, 45, False,
     "Bad back, sports injury, shoulder pain, physio, rehab after an operation"),
    ("Eye test", "Health & Wellbeing", 30, 30, False,
     "Eye test, new glasses, blurry vision, optician appointment"),
    ("Massage or sports therapy", "Health & Wellbeing", 50, 60, False,
     "Massage, stiff neck, sports massage, deep tissue"),

    # ── Community ────────────────────────────────────────────────────────────
    ("Community hall booking", "Community", 35, 180, False,
     "Hire the hall, book a room, party venue, meeting room, community centre"),
    ("Class or workshop place", "Community", 12, 90, False,
     "Yoga class, art class, evening course, workshop, exercise group"),
    ("Advice appointment", "Community", 0, 45, False,
     "Benefits advice, housing advice, citizens advice, help with a form, debt advice"),

    # ── Cleaning & Garden ────────────────────────────────────────────────────
    ("House clean", "Cleaning & Garden", 60, 120, False,
     "House clean, regular cleaner, deep clean, end of tenancy clean, "
     "moving out clean, spring clean"),
    ("Carpet or upholstery clean", "Cleaning & Garden", 80, 120, False,
     "Carpet cleaning, stain on the sofa, upholstery clean, rug cleaned"),
    ("Window cleaning", "Cleaning & Garden", 25, 45, False,
     "Window cleaner, dirty windows, conservatory roof, gutters cleared"),
    ("Garden maintenance", "Cleaning & Garden", 55, 120, False,
     "Grass cut, hedge trimmed, overgrown garden, weeding, garden tidy up"),
    ("Waste or rubbish removal", "Cleaning & Garden", 90, 90, False,
     "Rubbish removal, house clearance, take away the old sofa, garden waste, skip"),

    # ── Motoring ─────────────────────────────────────────────────────────────
    ("Car service", "Motoring", 140, 180, False,
     "Car service, full service, interim service, car due a service"),
    ("Mobile mechanic call out", "Motoring", 70, 60, True,
     "Car will not start, warning light, breakdown, strange noise from the engine, "
     "flat battery, car making a grinding sound"),
    ("Tyres fitted", "Motoring", 60, 45, False,
     "New tyres, puncture, flat tyre, tyre replacement, worn tyres"),
    ("Vehicle inspection", "Motoring", 45, 60, False,
     "Pre purchase inspection, check a car before I buy it, roadworthiness"),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    reset = "--reset" in sys.argv

    try:
        if reset:
            removed = db.query(Service).delete()
            db.commit()
            print(f"removed {removed} existing service(s)")

        # Categories are what the filter chips are built from, so they need real
        # rows rather than a hash. Numbered in the order listed, which is the
        # order the interface shows them in.
        from sqlalchemy import text as _text
        db.execute(_text(
            "CREATE TABLE IF NOT EXISTS categories ("
            " id BIGINT UNSIGNED PRIMARY KEY, name VARCHAR(120) NOT NULL,"
            " status TINYINT(1) NOT NULL DEFAULT 1)"
        ))
        names: list[str] = []
        for row in SERVICES:
            if row[1] not in names:
                names.append(row[1])
        ids = {name: i + 1 for i, name in enumerate(names)}
        for name, cid in ids.items():
            db.execute(_text(
                "INSERT INTO categories (id, name) VALUES (:id, :n) "
                "ON DUPLICATE KEY UPDATE name = :n"
            ), {"id": cid, "n": name})
        db.commit()

        existing = {s.name for s in db.query(Service.name).all()}
        added = 0
        for name, category, price, minutes, emergency, words in SERVICES:
            if name in existing:
                continue
            db.add(Service(
                name=name,
                description=words,
                price=price,
                duration_minutes=minutes,
                emergency=emergency,
                status=True,
                store_id=0,
                category_id=ids[category],
                stock=UNLIMITED,
            ))
            added += 1
        db.commit()
        print(f"{added} service(s) added, {db.query(Service).count()} in total")
    finally:
        db.close()


if __name__ == "__main__":
    main()
