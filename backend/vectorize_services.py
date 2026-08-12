"""Give every service an embedding, so the matching engine can find it.

The engine compares what a customer said against each service's embedding. A
service with no embedding is invisible to it, which is why a freshly seeded
database answers every question with "I could not find anything".

Run after seeding, and again after editing a description, because the
description is the part that carries the words customers actually use.

    python vectorize_services.py
"""

from app.db.database import SessionLocal
from app.services.rag import index_all_products


def main() -> None:
    db = SessionLocal()
    try:
        done = index_all_products(db)
        print(f"embedded {done} service(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
