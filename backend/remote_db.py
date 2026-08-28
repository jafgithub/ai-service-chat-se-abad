"""
Connection helpers for the outbox sync.

Lifted from the grocery product, where this has been running since 5 August, and
left as close to that version as possible on purpose: the two boxes share a
shape of problem, and a helper that has already survived a client's live
database is worth more than a tidier one that has not.

The script runs standalone (systemd), outside the FastAPI app, so it reads .env
directly with python-dotenv rather than importing app.core.config.

Two databases are in play:
  LOCAL  - the assistant's own MySQL on the box (DB_*), where it reads and writes.
  REMOTE - the client's GoDaddy MariaDB (REMOTE_DB_*), a copy for their systems.

Note the difference from the grocery instance: there the remote is the system of
record and we import from it. Here the remote is downstream of us. Nothing reads
back, which is why this file has no import helper.
"""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

# MySQL 8 rejects the '0000-00-00' dates that the client's MariaDB is full of.
# Relaxing sql_mode on our side of the wire is what lets those rows land at all;
# the scripts additionally coerce zero-dates to NULL so we don't store junk.
_PERMISSIVE_SQL_MODE = "SET SESSION sql_mode = ''"

_COMMON = dict(
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    connect_timeout=30,
    read_timeout=120,
    write_timeout=120,
)


def local_conn(autocommit: bool = False):
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", 3306)),
        database=os.getenv("DB_NAME", ""),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        init_command=_PERMISSIVE_SQL_MODE,
        autocommit=autocommit,
        **_COMMON,
    )


def remote_conn(autocommit: bool = False):
    host = os.getenv("REMOTE_DB_HOST", "")
    if not host:
        raise RuntimeError(
            "REMOTE_DB_HOST is not set. Add the REMOTE_DB_* block to backend/.env "
            "before running the import or sync scripts."
        )
    return pymysql.connect(
        host=host,
        port=int(os.getenv("REMOTE_DB_PORT", 3306)),
        database=os.getenv("REMOTE_DB_NAME", ""),
        user=os.getenv("REMOTE_DB_USER", ""),
        password=os.getenv("REMOTE_DB_PASSWORD", ""),
        autocommit=autocommit,
        **_COMMON,
    )


def shared_columns(local, remote, table: str) -> list[str]:
    """
    Columns present on BOTH sides, in the local table's ordinal order.

    Reading this from information_schema instead of hard-coding the list means the
    scripts keep working when the client adds a column on his side (we ignore it)
    or when we add one on ours (we skip it rather than crashing).
    """
    def cols(conn, db_env: str) -> list[str]:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME, ORDINAL_POSITION FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                (os.getenv(db_env, ""), table),
            )
            return [r["COLUMN_NAME"] for r in cur.fetchall()]

    local_cols  = cols(local, "DB_NAME")
    remote_cols = set(cols(remote, "REMOTE_DB_NAME"))
    if not local_cols:
        raise RuntimeError(f"Table '{table}' not found in the local database.")
    if not remote_cols:
        raise RuntimeError(f"Table '{table}' not found in the remote database.")
    return [c for c in local_cols if c in remote_cols]


def clean_zero_dates(row: dict, fields: tuple[str, ...]) -> dict:
    """Turn MariaDB's '0000-00-00[ 00:00:00]' placeholders into NULL."""
    for f in fields:
        v = row.get(f)
        if v is not None and str(v).startswith("0000-00-00"):
            row[f] = None
    return row
