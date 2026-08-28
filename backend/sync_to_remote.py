"""
Drain sync_outbox: push locally created Service Assistant rows to the client's
remote (GoDaddy) database.

Lifted from the grocery product's sync_to_remote.py, which has run against a
live client database since 5 August, and kept as close to it as the different
schema allows. The parts worth keeping are the parts that were learned the hard
way: the outbox so a slow remote never fails a booking, the id map because both
databases auto increment independently, the deferred retry for a child that
reaches the queue before its parent, and the backoff.

The one real change is that the three hand written handlers became one, driven
by the table below. The grocery has three tables; this has fifteen, and fifteen
near identical functions is fifteen places for one of them to be subtly wrong.

Usage (run from backend/, inside the venv):
    python sync_to_remote.py --once            # single pass, then exit
    python sync_to_remote.py --interval 60     # loop (how systemd runs it)
    python sync_to_remote.py --backfill --once # enqueue pre-existing rows first
"""

import argparse
import time
import traceback

import pymysql

from remote_db import local_conn, remote_conn, shared_columns

#: Parents before children. The outbox is drained in id order, so this is the
#: order rows are enqueued in on a backfill; a child that still arrives first is
#: caught by Deferred and retried.
TABLES = (
    "accounts", "categories", "stores", "customers", "providers", "services",
    "provider_availability", "provider_services", "provider_time_off",
    "service_requests", "jobs", "job_lines", "appointments", "payments",
    "parking_passes",
)

#: Which columns are foreign keys, and to what. Every one of these is translated
#: through sync_id_map on the way out, because a local id means nothing remotely.
#:
#: Read out of the database rather than guessed: only 9 of these are declared as
#: constraints. The other 6 are foreign keys in every sense except the one MySQL
#: knows about, and those are exactly the ones that would have carried a local id
#: to the remote and quietly pointed at somebody else's row.
#:
#: Deliberately absent, having been checked in the models:
#:   appointments.technician_id  plain Integer, no table behind it
#:   services.unit_id/module_id  legacy columns inherited from the grocery fork
#:   payments.provider_event_id  a Stripe event reference, not a local row
#:   service_requests.session_id points at chat_sessions, which is not synced
PARENTS: dict[str, dict[str, str]] = {
    "accounts": {},
    "categories": {},
    "stores": {},
    "customers": {},
    "providers": {},
    "services": {"category_id": "categories", "store_id": "stores"},
    "provider_availability": {"provider_id": "providers"},
    "provider_services": {"provider_id": "providers", "service_id": "services"},
    "provider_time_off": {"provider_id": "providers"},
    "service_requests": {"customer_id": "customers", "service_id": "services",
                         "provider_id": "providers", "job_id": "jobs"},
    "jobs": {"customer_id": "customers", "provider_id": "providers",
             "provider_service_id": "provider_services",
             "service_request_id": "service_requests"},
    "job_lines": {"job_id": "jobs", "item_id": "services"},
    "appointments": {"job_id": "jobs", "provider_id": "providers"},
    "payments": {"order_id": "jobs"},
    "parking_passes": {"account_id": "accounts", "customer_id": "customers"},
}

#: Columns that must never leave this box, whatever the schema says. Stripped
#: from every row on the way out.
NEVER_SEND = {"password_hash", "token_hash", "hashed_password"}

#: Tables whose primary key is assigned rather than generated. Everything else
#: is AUTO_INCREMENT on both sides, so the remote picks its own id and the map
#: records the translation. These two are not, so an insert that leaves `id` out
#: sends 0 and the second row collides with the first:
#:
#:   pymysql.err.IntegrityError (1062, "Duplicate entry '0' for key 'PRIMARY'")
#:
#: They are catalogue tables inherited from the grocery fork, where the id is
#: the identity rather than a surrogate, so it is carried across unchanged and
#: the map is an identity mapping. Same reasoning as item_id over there.
KEEP_ID = {"categories", "stores"}

#: `jobs` and `service_requests` point at each other. Whichever is inserted
#: first cannot know the other's remote id, so the key is left NULL and filled
#: in by the update the second insert enqueues.
SOFT = {("jobs", "service_request_id"), ("service_requests", "job_id")}

BATCH_LIMIT   = 200
MAX_ATTEMPTS  = 8
MAX_BACKOFF_MINUTES = 15


class Deferred(Exception):
    """Row can't sync yet because its parent hasn't synced - retry shortly."""


def log(msg: str) -> None:
    print(f"[sync] {msg}", flush=True)


# ── id map ────────────────────────────────────────────────────────────────────

def get_remote_id(local, table: str, local_id: int) -> int | None:
    with local.cursor() as cur:
        cur.execute(
            "SELECT remote_id FROM sync_id_map WHERE table_name = %s AND local_id = %s",
            (table, local_id),
        )
        row = cur.fetchone()
    return row["remote_id"] if row else None


def set_remote_id(local, table: str, local_id: int, remote_id: int) -> None:
    with local.cursor() as cur:
        cur.execute(
            "INSERT INTO sync_id_map (table_name, local_id, remote_id) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE remote_id = VALUES(remote_id)",
            (table, local_id, remote_id),
        )
    local.commit()


# ── row helpers ───────────────────────────────────────────────────────────────

def read_local_row(local, table: str, local_id: int, columns: list[str]) -> dict | None:
    col_sql = ", ".join(f"`{c}`" for c in columns)
    with local.cursor() as cur:
        cur.execute(f"SELECT {col_sql} FROM `{table}` WHERE id = %s", (local_id,))
        return cur.fetchone()


def remote_insert(remote, table: str, row: dict, keep_id: bool = False) -> int:
    """INSERT, normally without `id` so the remote assigns its own.

    `keep_id` is for the tables in KEEP_ID, whose primary key is meaningful and
    is carried across unchanged.
    """
    payload = dict(row) if keep_id else {k: v for k, v in row.items() if k != "id"}
    col_sql = ", ".join(f"`{c}`" for c in payload)
    marks   = ", ".join(["%s"] * len(payload))
    with remote.cursor() as cur:
        cur.execute(f"INSERT INTO `{table}` ({col_sql}) VALUES ({marks})",
                    tuple(payload.values()))
        remote.commit()
        return row["id"] if keep_id else cur.lastrowid


def remote_update(remote, table: str, remote_id: int, row: dict) -> None:
    payload = {k: v for k, v in row.items() if k != "id"}
    set_sql = ", ".join(f"`{c}` = %s" for c in payload)
    with remote.cursor() as cur:
        cur.execute(f"UPDATE `{table}` SET {set_sql} WHERE id = %s",
                    (*payload.values(), remote_id))
    remote.commit()


# ── the one handler ───────────────────────────────────────────────────────────

def sync_row(local, remote, table: str, local_id: int, op: str, columns: list[str]) -> str:
    row = read_local_row(local, table, local_id, columns)
    if row is None:
        return "row gone locally, skipped"

    for column, parent in PARENTS[table].items():
        if column not in row or row[column] is None:
            continue
        parent_remote_id = get_remote_id(local, parent, row[column])
        if parent_remote_id is None:
            if (table, column) in SOFT:
                # Filled in by the update the other side of the cycle enqueues.
                row[column] = None
                continue
            raise Deferred(f"{parent} {row[column]} not synced yet")
        row[column] = parent_remote_id

    for secret in NEVER_SEND:
        row.pop(secret, None)

    remote_id = get_remote_id(local, table, local_id)
    if remote_id is None:
        keep = table in KEEP_ID
        if keep:
            # It may already be there from a previous life of this database.
            # Adopting beats colliding, and the id is the identity either way.
            with remote.cursor() as cur:
                cur.execute(f"SELECT id FROM `{table}` WHERE id = %s", (local_id,))
                if cur.fetchone():
                    set_remote_id(local, table, local_id, local_id)
                    remote_update(remote, table, local_id, row)
                    return f"adopted existing remote {table} {local_id}"
        remote_id = remote_insert(remote, table, row, keep_id=keep)
        set_remote_id(local, table, local_id, remote_id)
        return f"inserted remote {table} {remote_id}"

    remote_update(remote, table, remote_id, row)
    return f"updated remote {table} {remote_id}"


# ── outbox bookkeeping ────────────────────────────────────────────────────────

def claim_batch(local) -> list[dict]:
    # MySQL defaults to REPEATABLE READ, so a transaction left open by the previous
    # pass would pin this connection's snapshot and the worker would never see rows
    # enqueued after it started. Ending it first is what makes the poll actually poll.
    local.commit()
    with local.cursor() as cur:
        cur.execute(
            "SELECT id, table_name, local_id, op, attempts FROM sync_outbox "
            "WHERE status = 'pending' "
            "  AND (next_attempt_at IS NULL OR next_attempt_at <= NOW()) "
            "ORDER BY id LIMIT %s",
            (BATCH_LIMIT,),
        )
        return cur.fetchall()


def mark_done(local, outbox_id: int) -> None:
    with local.cursor() as cur:
        cur.execute(
            "UPDATE sync_outbox SET status = 'done', synced_at = NOW(), last_error = NULL "
            "WHERE id = %s",
            (outbox_id,),
        )
    local.commit()


def mark_retry(local, entry: dict, error: str, short: bool = False) -> None:
    """Exponential backoff, or a short fixed delay when we're just waiting on a parent."""
    attempts = entry["attempts"] + 1
    if not short and attempts >= MAX_ATTEMPTS:
        status, delay_expr = "failed", "NULL"
    else:
        status = "pending"
        minutes = 1 if short else min(2 ** (attempts - 1), MAX_BACKOFF_MINUTES)
        delay_expr = f"DATE_ADD(NOW(), INTERVAL {minutes} MINUTE)"

    with local.cursor() as cur:
        cur.execute(
            f"UPDATE sync_outbox SET status = %s, attempts = %s, last_error = %s, "
            f"next_attempt_at = {delay_expr} WHERE id = %s",
            (status, attempts, error[:2000], entry["id"]),
        )
    local.commit()
    if status == "failed":
        log(f"! outbox {entry['id']} ({entry['table_name']} {entry['local_id']}) "
            f"FAILED after {attempts} attempts: {error}")


def backfill(local) -> int:
    """
    Enqueue every pre-existing row that has never been mapped, so history already
    sitting in the local database can be pushed once.

    Walks TABLES in order, which is parents before children, so the FIFO drain
    mostly resolves parents first. Mostly, not always: jobs and service_requests
    reference each other, so one of them is always enqueued before the row it
    points at exists remotely. That is what SOFT and Deferred are for.
    """
    inserted = 0
    with local.cursor() as cur:
        for table in TABLES:
            cur.execute(
                f"INSERT INTO sync_outbox (table_name, local_id, op) "
                f"SELECT %s, t.id, 'insert' FROM `{table}` t "
                f"LEFT JOIN sync_id_map m ON m.table_name = %s AND m.local_id = t.id "
                f"WHERE m.remote_id IS NULL "
                f"  AND NOT EXISTS (SELECT 1 FROM sync_outbox o "
                f"                  WHERE o.table_name = %s AND o.local_id = t.id "
                f"                    AND o.status = 'pending') "
                f"ORDER BY t.id",
                (table, table, table),
            )
            log(f"backfill: enqueued {cur.rowcount} rows from {table}")
            inserted += cur.rowcount
    local.commit()
    return inserted


# ── main loop ─────────────────────────────────────────────────────────────────

def run_pass(local, remote, columns: dict[str, list[str]]) -> int:
    remote.commit()  # same snapshot reason as claim_batch, for the remote lookups
    entries = claim_batch(local)
    if not entries:
        return 0

    for entry in entries:
        table = entry["table_name"]
        if table not in PARENTS:
            mark_retry(local, entry, f"unknown table '{table}'")
            continue
        try:
            result = sync_row(local, remote, table, entry["local_id"],
                              entry["op"], columns[table])
            mark_done(local, entry["id"])
            log(f"{table} {entry['local_id']} -> {result}")
        except Deferred as exc:
            mark_retry(local, entry, str(exc), short=True)
        except (pymysql.err.OperationalError, pymysql.err.InterfaceError):
            # Connection-level problem: stop the batch, let the next tick reconnect.
            mark_retry(local, entry, traceback.format_exc(limit=2))
            raise
        except Exception:
            mark_retry(local, entry, traceback.format_exc(limit=3))

    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push local Service Assistant rows to the remote database.")
    parser.add_argument("--once", action="store_true", help="single pass, then exit")
    parser.add_argument("--interval", type=int, default=60, help="seconds between passes")
    parser.add_argument("--backfill", action="store_true",
                        help="enqueue existing unmapped rows before draining")
    args = parser.parse_args()

    local = remote = None
    columns: dict[str, list[str]] = {}
    try:
        while True:
            try:
                if local is None:
                    local = local_conn()
                if remote is None:
                    remote = remote_conn()
                    columns = {t: [c for c in shared_columns(local, remote, t)] for t in TABLES}
                    log("connected; shared columns: "
                        + ", ".join(f"{t}={len(columns[t])}" for t in TABLES))

                if args.backfill:
                    backfill(local)
                    args.backfill = False  # once per process

                processed = run_pass(local, remote, columns)
                if processed:
                    log(f"pass complete — {processed} outbox rows handled")

            except Exception as exc:
                log(f"! pass aborted: {exc}")
                for conn in (local, remote):
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                local = remote = None

            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log("stopped")
    finally:
        for conn in (local, remote):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
