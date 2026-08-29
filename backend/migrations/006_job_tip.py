"""What the customer added for the provider, kept apart from the price.

A tip is not a price change. `jobs.total_amount` is what the customer pays and
has to stay that, because `api/payments.py` builds the Stripe and PayPal charge
from it and from nothing else. But a total that silently contains a gratuity is
no use to anybody afterwards: the provider cannot tell what they were tipped,
and the office cannot tell what the work was sold for.

So the tip gets its own column and `total_amount` becomes price + tip.

    jobs.tip_amount   what was added for the provider, 0 when nothing was

NOT NULL with a default of 0, unlike migration 005's nullable columns. Every
existing job was booked before tips existed, and "no tip" is the honest reading
of that, not "unknown". It also means every sum over the column works without a
COALESCE.

Run this BEFORE deploying the model change. SQLAlchemy selects every mapped
column, so a `Job` model naming a column the database has not got turns every
booking query into a 500, not just the new ones.

Re-runnable, like the others: it asks `information_schema` first and does
nothing for a column that is already there.

    .venv/bin/python migrations/006_job_tip.py
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


COLUMNS = (
    ("tip_amount", "DECIMAL(10,2) NOT NULL DEFAULT 0"),
)


def main() -> None:
    with engine.begin() as conn:
        for column, definition in COLUMNS:
            if column_exists(conn, "jobs", column):
                print(f"jobs.{column} already exists, nothing to do")
                continue
            conn.execute(text(
                f"ALTER TABLE jobs ADD COLUMN {column} {definition}"
            ))
            print(f"added jobs.{column}")


if __name__ == "__main__":
    main()
