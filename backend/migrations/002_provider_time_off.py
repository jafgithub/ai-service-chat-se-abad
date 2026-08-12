"""Breaks and closures, and the index the diary reads on every request.

Working hours say when a business is normally open. They cannot say "closed
Tuesday afternoon for training" or "back on the 8th", and a diary that only
knows the normal pattern will cheerfully sell an hour nobody is there for.

Re-runnable and non-destructive, like 001.

    python migrations/002_provider_time_off.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402

STATEMENTS = [
    ("provider_time_off table", """
        CREATE TABLE IF NOT EXISTS provider_time_off (
          id INT AUTO_INCREMENT PRIMARY KEY,
          provider_id INT NOT NULL,
          starts_at DATETIME NOT NULL,
          ends_at   DATETIME NOT NULL,
          reason VARCHAR(200),
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          INDEX ix_time_off_provider (provider_id, starts_at, ends_at),
          CONSTRAINT fk_time_off_provider FOREIGN KEY (provider_id)
            REFERENCES providers(id) ON DELETE CASCADE
        )
    """),
    # Availability is read per provider on every slot calculation, and the
    # existing index is on the unique constraint, which leads with provider_id
    # already. This one covers the lookup by provider and weekday directly.
    ("appointment lookup by provider", """
        CREATE INDEX ix_appointment_provider ON appointments (provider_id, starts_at)
    """),
]


def main() -> None:
    db = SessionLocal()
    try:
        for label, ddl in STATEMENTS:
            try:
                db.execute(text(ddl))
                db.commit()
                print(f"  {label}")
            except Exception as exc:  # noqa: BLE001
                # CREATE INDEX has no IF NOT EXISTS in MySQL, so a second run
                # raises rather than doing nothing. That is not a failure.
                if "Duplicate key name" in str(exc) or "already exists" in str(exc):
                    db.rollback()
                    print(f"  {label} already there")
                else:
                    raise

        for table in ("provider_time_off", "providers", "provider_services",
                      "provider_availability", "appointments", "jobs", "customers"):
            n = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table:24} {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
