"""Providers, provider services, availability, accounts and sessions.

Written as re-runnable statements rather than a one-shot script: every table is
CREATE TABLE IF NOT EXISTS and every column is added only after checking
information_schema. Running it twice changes nothing, which matters because it
will be run by hand on a live database more than once.

Nothing is dropped and nothing is rewritten. The existing services, jobs,
appointments and customers keep their rows; jobs and appointments gain a
nullable provider_id, so the one booking already taken stays valid with no
provider attached.

    python migrations/001_providers_and_accounts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402

TABLES = [
    ("providers", """
        CREATE TABLE IF NOT EXISTS providers (
          id INT AUTO_INCREMENT PRIMARY KEY,
          business_name VARCHAR(200) NOT NULL,
          contact_name  VARCHAR(160),
          email         VARCHAR(255) NOT NULL UNIQUE,
          phone         VARCHAR(40),
          website       VARCHAR(400),
          description   TEXT,
          address       TEXT,
          city          VARCHAR(120),
          postcode      VARCHAR(20),
          latitude      DECIMAL(10,7),
          longitude     DECIMAL(10,7),
          travel_radius_miles INT DEFAULT 15,
          status ENUM('pending','active','suspended','rejected') NOT NULL DEFAULT 'pending',
          requires_approval TINYINT(1) NOT NULL DEFAULT 0,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          INDEX ix_provider_status (status)
        )
    """),
    ("provider_services", """
        CREATE TABLE IF NOT EXISTS provider_services (
          id INT AUTO_INCREMENT PRIMARY KEY,
          provider_id INT NOT NULL,
          service_id  INT NOT NULL,
          price DECIMAL(10,2),
          duration_minutes INT,
          notes TEXT,
          active TINYINT(1) NOT NULL DEFAULT 1,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          UNIQUE KEY uq_provider_service (provider_id, service_id),
          INDEX ix_provider_service_service (service_id, active),
          CONSTRAINT fk_ps_provider FOREIGN KEY (provider_id)
            REFERENCES providers(id) ON DELETE CASCADE
        )
    """),
    ("provider_availability", """
        CREATE TABLE IF NOT EXISTS provider_availability (
          id INT AUTO_INCREMENT PRIMARY KEY,
          provider_id INT NOT NULL,
          weekday   INT NOT NULL,
          opens_at  TIME NOT NULL,
          closes_at TIME NOT NULL,
          out_of_hours TINYINT(1) NOT NULL DEFAULT 0,
          UNIQUE KEY uq_provider_weekday (provider_id, weekday, opens_at),
          CONSTRAINT fk_pa_provider FOREIGN KEY (provider_id)
            REFERENCES providers(id) ON DELETE CASCADE
        )
    """),
    ("accounts", """
        CREATE TABLE IF NOT EXISTS accounts (
          id INT AUTO_INCREMENT PRIMARY KEY,
          email VARCHAR(255) NOT NULL UNIQUE,
          password_hash VARCHAR(255) NOT NULL,
          role ENUM('customer','provider','admin') NOT NULL DEFAULT 'customer',
          customer_id INT,
          provider_id INT,
          last_login_at DATETIME,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          INDEX ix_account_role (role)
        )
    """),
    ("sessions", """
        CREATE TABLE IF NOT EXISTS sessions (
          id INT AUTO_INCREMENT PRIMARY KEY,
          account_id INT NOT NULL,
          token_hash VARCHAR(64) NOT NULL UNIQUE,
          expires_at DATETIME NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          revoked_at DATETIME,
          INDEX ix_session_account (account_id),
          INDEX ix_session_expiry (expires_at),
          CONSTRAINT fk_session_account FOREIGN KEY (account_id)
            REFERENCES accounts(id) ON DELETE CASCADE
        )
    """),
]

# Nullable on purpose. The booking already taken has no provider, and a column
# that refuses that would mean either deleting it or inventing a provider for
# it. Both are worse than a null that says "before providers existed".
COLUMNS = [
    ("jobs", "provider_id", "INT NULL"),
    ("appointments", "provider_id", "INT NULL"),
    # Which of the provider's own offerings was booked, so a price change later
    # does not rewrite what somebody was quoted.
    ("jobs", "provider_service_id", "INT NULL"),
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
                WHERE table_schema = DATABASE()
                  AND table_name = :t AND column_name = :c
            """), {"t": table, "c": column}).scalar()
            if exists:
                print(f"  {table}.{column} already there")
                continue
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {spec}"))
            print(f"  {table}.{column} added")
        db.commit()

        counts = {}
        for t in ("providers", "provider_services", "provider_availability",
                  "accounts", "sessions", "customers", "jobs", "appointments"):
            counts[t] = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        print("\nrow counts after migration:")
        for t, n in counts.items():
            print(f"  {t:24} {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
