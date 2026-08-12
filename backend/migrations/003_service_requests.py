"""Service requests, and the currency a booking was agreed in.

A request is a problem somebody described. It exists before any booking and
often instead of one, which is why it needs its own table rather than living in
`jobs`: the requests that never became bookings are the ones that show where
there is no cover.

Currency is stored on the job rather than read from configuration at display
time, so a historic booking still reads in the currency it was agreed in if the
platform ever takes a second one.

Re-runnable and non-destructive.

    python migrations/003_service_requests.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402

TABLES = [
    ("service_requests", """
        CREATE TABLE IF NOT EXISTS service_requests (
          id INT AUTO_INCREMENT PRIMARY KEY,
          customer_id INT NOT NULL,
          description TEXT NOT NULL,
          address TEXT,
          postcode VARCHAR(20),
          urgency ENUM('whenever','this_week','urgent') NOT NULL DEFAULT 'whenever',
          service_id INT,
          provider_id INT,
          job_id INT,
          status ENUM('open','matched','booked','unserved','closed')
            NOT NULL DEFAULT 'open',
          outcome_note TEXT,
          session_id VARCHAR(64),
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          INDEX ix_request_customer (customer_id, created_at),
          INDEX ix_request_status (status)
        )
    """),
]

COLUMNS = [
    ("jobs", "currency", f"VARCHAR(8) NULL DEFAULT '{settings.PAYMENT_CURRENCY}'"),
    ("jobs", "service_request_id", "INT NULL"),
]


def main() -> None:
    db = SessionLocal()
    try:
        for name, ddl in TABLES:
            db.execute(text(ddl))
            print(f"  table {name}")
        db.commit()

        for table, column, spec in COLUMNS:
            exists = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = :t
                  AND column_name = :c
            """), {"t": table, "c": column}).scalar()
            if exists:
                print(f"  {table}.{column} already there")
                continue
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {spec}"))
            print(f"  {table}.{column} added")
        db.commit()

        # Existing jobs predate the column and would otherwise read as having no
        # currency at all, which is worse than the platform default.
        filled = db.execute(text(
            "UPDATE jobs SET currency = :c WHERE currency IS NULL"
        ), {"c": settings.PAYMENT_CURRENCY}).rowcount
        db.commit()
        if filled:
            print(f"  {filled} existing job(s) given a currency")

        for t in ("service_requests", "jobs", "appointments", "customers",
                  "providers", "accounts"):
            n = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t:20} {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
