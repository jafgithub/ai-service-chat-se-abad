"""The management contact, indexed once, so it can be asked for.

The client asked the assistant for the management address and was refused. He
was right to complain: the address is on page one of the management pack, in
the letterhead, and that document is not a scan.

The text was never in the index. `doc_chunker.NOISE` strips the letterhead by
name, on purpose, because it repeats on every page and would otherwise make the
office address the most retrievable text in the document. That decision was
right. Throwing it away entirely was not.

So the rule changes from "drop the letterhead" to "keep exactly one copy of it,
as a contact". This adds that one copy to the live index, without rebuilding:
a rebuild from `build_doc_index.py` would drop every document uploaded through
the admin screen, which is a far worse thing to do than this fixes.

    .venv/bin/python scripts/add_management_contact.py

Re-runnable. The chunk carries a `doc_id`, so it is dropped before being added
again rather than appended twice: `add_chunks` has no upsert.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import docs_index, rag  # noqa: E402

#: One per community that actually prints a management contact on its paperwork.
#:
#: Kendall Square, Valencia and Enclave At Old Cutler are deliberately absent:
#: their only document is a Sherwin-Williams colour sheet with no management
#: details on it at all, and each holds exactly one chunk today, so inventing a
#: second one would change what their paint questions retrieve.
#:
#: `document_short` has to be a title the document library already holds, or an
#: answer citing it would offer a download that does not exist. "Rules and
#: Regulations (management pack)" maps to knowledge/serenity/application.pdf,
#: which is the document this letterhead actually heads, so the citation is the
#: truth rather than a convenient label.
#:
#: The wording was chosen by measurement rather than taste. The bare letterhead
#: scored 0.272 against "who manages this community", under the 0.30 retrieval
#: floor. The two words "Managing agent." lift that to 0.326 and improve every
#: other phrasing tested, while scoring 0.051 against "what are the quiet
#: hours", which is the number that matters: it cannot displace a rules answer.
CONTACTS = [
    {
        "doc_id": "serenity-managing-agent",
        "id": "serenity-managing-agent-1",
        "document": "Serenity Community Association Rules and Regulations",
        "document_short": "Rules and Regulations (management pack)",
        "approved": "",
        "section": "Managing agent",
        "community": "serenity",
        "text": (
            "Managing agent. L&C Royal Management Corporation, "
            "13155 SW 42nd Street Ste 103, Miami, FL 33175-3428. "
            "T (305) 228-7326 / (305) 228-7327. F (305) 228-7328. "
            "lcroyal@lcroyalmanagement.com"
        ),
    },
]


def main() -> None:
    for contact in CONTACTS:
        removed = docs_index.drop_document(contact["doc_id"])
        if removed:
            print(f"removed {removed} existing section(s) for {contact['doc_id']}")

        vectors = [rag.embed_text(contact["text"])]
        docs_index.add_chunks([contact], vectors)
        print(f"added {contact['section']} for {contact['community']}")

    print(f"{len(docs_index._chunks)} chunks in the index")


if __name__ == "__main__":
    main()
