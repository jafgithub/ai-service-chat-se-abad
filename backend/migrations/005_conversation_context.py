"""What the conversation is about, kept between turns.

`last_shown_json` already remembers the numbered list of services, which is what
makes "book item 2" resolve. The documents had no equivalent, so a resident who
was just told "what I hold for Kendall Square is the Approved colour archive"
and replied "can you download the color archive for me" was answered with "are
you asking about your community's rules, or do you need someone to come out?".
Nothing had kept the archive.

Three columns:

    community            which association this conversation is about
    last_documents_json  the documents last named, so "download that" resolves
    mode                 documents or services, so a follow-up stays where it belongs

`community` is duplicated in the browser's localStorage and sent on every text
request, which is not a reason to leave it there: `/voice` takes a session id
and an audio file and nothing else, so a spoken question was scoped to the home
community however the resident had answered the picker.

Re-runnable, like the others: it asks `information_schema` first and does
nothing for a column that is already there.

    .venv/bin/python migrations/005_conversation_context.py
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


#: Nullable every one of them. An existing conversation has no community, no
#: documents and no mode, and that is exactly what it should mean: decide again
#: on the next message rather than pretend to remember something.
COLUMNS = (
    ("community", "VARCHAR(64) NULL"),
    ("last_documents_json", "JSON NULL"),
    ("conversation_mode", "VARCHAR(16) NULL"),
)


def main() -> None:
    with engine.begin() as conn:
        for column, definition in COLUMNS:
            if column_exists(conn, "chat_sessions", column):
                print(f"chat_sessions.{column} already exists, nothing to do")
                continue
            conn.execute(text(
                f"ALTER TABLE chat_sessions ADD COLUMN {column} {definition}"
            ))
            print(f"added chat_sessions.{column}")


if __name__ == "__main__":
    main()
