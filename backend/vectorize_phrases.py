"""Give every phrase its own vector.

Run after seeding, and again whenever a description changes, because the
phrases are the thing being embedded.

    python vectorize_phrases.py
"""

import json

from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.phrase_index import split_phrases
from app.services.rag import embed_text


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS service_phrases (
              id         BIGINT AUTO_INCREMENT PRIMARY KEY,
              service_id BIGINT NOT NULL,
              phrase     VARCHAR(400) NOT NULL,
              vector     JSON NOT NULL,
              INDEX ix_phrase_service (service_id)
            )
        """))
        db.execute(text("DELETE FROM service_phrases"))
        db.commit()

        rows = db.execute(text(
            "SELECT id, name, description FROM services WHERE status = 1"
        )).fetchall()

        total = 0
        for service_id, name, description in rows:
            for phrase in split_phrases(name or "", description or ""):
                db.execute(
                    text("INSERT INTO service_phrases (service_id, phrase, vector) "
                         "VALUES (:s, :p, :v)"),
                    {"s": service_id, "p": phrase[:400],
                     "v": json.dumps(embed_text(phrase))},
                )
                total += 1
        db.commit()
        print(f"{total} phrases embedded across {len(rows)} services")
    finally:
        db.close()


if __name__ == "__main__":
    main()
