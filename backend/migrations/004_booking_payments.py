"""Payment state for a booking.

`jobs.status` already carries the booking's own lifecycle: scheduled, cancelled,
completed. Paying is a second, independent fact about the same row, and the shop
got away with conflating them only because an order had nothing else to be. A
visit that is booked and unpaid, or booked and paid, or cancelled after being
paid, are all real and all different.

Re-runnable, like the others: it asks `information_schema` first and does
nothing when the column is already there.

    .venv/bin/python migrations/004_booking_payments.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db.database import engine  # noqa: E402


def column_exists(conn, table: str, column: str) -> bool:
    found = conn.execute(text("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c
    """), {"t": table, "c": column}).scalar()
    return bool(found)


def main() -> None:
    with engine.begin() as conn:
        if column_exists(conn, "jobs", "payment_status"):
            print("jobs.payment_status already exists, nothing to do")
        else:
            conn.execute(text("""
                ALTER TABLE jobs
                ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid'
            """))
            print("added jobs.payment_status")

            # Everything booked before this existed was taken without payment,
            # which is exactly what 'unpaid' means, so the default is already
            # right for them. Cash jobs from the shop are the exception: they
            # were always going to be settled at the door.
            updated = conn.execute(text("""
                UPDATE jobs SET payment_status = 'cod' WHERE payment_method = 'cod'
            """)).rowcount
            print(f"marked {updated} existing cash job(s) as cod")

        rows = conn.execute(text("""
            SELECT payment_status, COUNT(*) FROM jobs GROUP BY payment_status
        """)).all()
        print("jobs by payment status:", {r[0]: r[1] for r in rows})


if __name__ == "__main__":
    main()
