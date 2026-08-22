"""The community documents, held in memory and searched by meaning.

Eighty one chunks and 384 dimensions is 124 KB of floats. Holding it in RAM and
doing the whole search with one matrix multiply is both simpler and faster than
any store we could add, and it follows what `catalog_index` already does for
the service catalogue, so there is one pattern here rather than two.

The index is built offline by `scripts/build_doc_index.py` and shipped as JSON.
Nothing is embedded at startup except the query, and the model is the same
`all-MiniLM-L6-v2` that `rag.py` already loads, so this costs no new dependency,
no API call and no extra memory for weights.
"""

import json
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("docs")

INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "serenity_docs.json"

# Below this, the best chunk is not really about the question. Chosen by running
# the real questions in tests/test_docs_index.py: genuine questions score 0.35
# to 0.75, and things the documents say nothing about ("do you offer wifi",
# "what time does the pool close" where no closing time is stated) sit under
# 0.30. The gap is comfortable, and the cost of being wrong is asymmetric: a
# refusal is a small annoyance, an invented rule about someone's home is not.
MIN_SCORE = 0.30

# The community the assistant speaks for. Chunks from anywhere else are indexed
# but not searched unless the question names that place, because the client sent
# a City of Lauderdale Lakes code handbook along with the Serenity documents and
# Serenity Point is in Miami Lakes. A resident asking about their own bin day
# must not be answered out of another city's ordinances.
HOME_COMMUNITY = "serenity"


@dataclass(frozen=True)
class Community:
    """A place a resident might name, and what the assistant calls it back.

    `key` is the tag carried by a chunk, so a community is "available" exactly
    when the index holds chunks for it. Nothing here declares availability;
    `available()` reads it off the loaded index, which means adding a document
    makes its community answerable without touching this list.
    """

    key: str
    label: str
    aliases: tuple[str, ...]


REGISTRY_PATH = INDEX_PATH.parent / "communities.json"

# Every community the assistant recognises by name, including any it has no
# documents for. Naming the ones we cannot answer is the point: a community has
# to be recognised in order to be refused, because the alternative is what the
# client saw in August, a Three Lakes question answered out of the Serenity
# rules because "Lake" is close to "lakes" in the embedding space.
#
# **Data, not code.** It lives in `communities.json` beside the index, because an
# administrator uploading the first document for a new association has to be
# able to register its name in the same breath. While this was a tuple in the
# source, that could only happen by editing Python and redeploying, and the
# failure when somebody forgot was silent: the name went unrecognised and every
# question about that association was answered from Serenity's rules.
COMMUNITIES: tuple[Community, ...] = ()


def _load_registry() -> tuple[Community, ...]:
    """Read the registry, or fall back to the home community alone.

    A missing or unreadable file must not leave the assistant with no names at
    all, because with no names every question resolves to home and one
    association's rules start answering for another. Home alone is the safe
    floor: it answers Serenity and refuses to recognise anybody else.
    """
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        found = tuple(
            Community(c["key"], c["label"], tuple(c.get("aliases") or [c["key"]]))
            for c in data.get("communities", [])
            if c.get("key") and c.get("label")
        )
        if found:
            return found
        logger.warning("[DOCS] %s holds no communities", REGISTRY_PATH)
    except FileNotFoundError:
        logger.warning("[DOCS] no registry at %s", REGISTRY_PATH)
    except Exception:  # noqa: BLE001 - a broken file must not take the app down
        logger.exception("[DOCS] registry unreadable")
    return (Community(HOME_COMMUNITY, "Serenity Point", ("serenity", "serenity point")),)


def reload_registry() -> int:
    """Re-read the registry. Called after an upload adds a community."""
    global COMMUNITIES
    COMMUNITIES = _load_registry()
    logger.info("[DOCS] registry: %d communities", len(COMMUNITIES))
    return len(COMMUNITIES)


COMMUNITIES = _load_registry()

# Words that decorate a community's name without identifying it. Stripped from
# both sides, so "Serenity Point" and "serenity" are one name, and so is
# "Three Lakes Community".
_FILLER = frozenset({
    "the", "a", "an", "of", "in", "at", "for", "my", "our", "this",
    "city", "town", "community", "communities", "association", "hoa",
    "homeowners", "homeowner", "point", "village", "estates", "estate",
    "subdivision", "neighbourhood", "neighborhood",
})


def _words(text: str) -> list[str]:
    """A phrase reduced to identifying words: lowercased, singular, no filler.

    The singular rule is deliberately crude. It only has to make "lakes" and
    "lake" the same word, which is the whole of the bug it was written for:
    the client typed "Lauderdale Lake" and the tag said "lauderdale lakes", so
    the substring test that used to live here missed by one letter and the
    question was answered from Serenity instead.
    """
    out = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        if word not in _FILLER:
            out.append(word)
    return out


def _contains(haystack: list[str], needle: list[str]) -> bool:
    """Is `needle` present in `haystack` as consecutive words?

    Word sequences rather than a substring, so "Lakeview Drive" cannot match
    "lake" and a name only matches where it was actually written.
    """
    if not needle or len(needle) > len(haystack):
        return False
    return any(haystack[i:i + len(needle)] == needle
               for i in range(len(haystack) - len(needle) + 1))


def named_communities(query: str) -> list[Community]:
    """Every community the question names, in the order they are declared.

    More than one is a fair question ("how does Lauderdale Lakes handle bins
    compared to us"), so this returns a list rather than picking a winner.
    """
    words = _words(query or "")
    found = []
    for community in COMMUNITIES:
        if any(_contains(words, _words(alias)) for alias in community.aliases):
            found.append(community)
    return found


def available() -> set[str]:
    """The communities the index actually holds documents for."""
    if not _load():
        return set()
    return {c.get("community", HOME_COMMUNITY) for c in _chunks}


def label_for(key: str) -> str:
    """The community's name as a resident would say it, from its tag.

    Chunks carry the tag ("lauderdale lakes"); people read the label
    ("Lauderdale Lakes"). An unknown tag is title cased rather than dropped, so
    a community added to the index before it is added to the registry still
    shows something truthful.
    """
    for community in COMMUNITIES:
        if community.key == key:
            return community.label
    return key.title()


def documents_for(key: str) -> list[str]:
    """The titles a community's chunks came from, in the order they appear.

    Used to tell a resident what is actually in scope when their question found
    nothing. "I could not find that" is a dead end; "I hold the Code Compliance
    Handbook, ask me about parking or bins" is a next step, and it is still
    only ever the truth about what the index holds.
    """
    if not _load():
        return []
    titles = []
    for chunk in _chunks:
        if chunk.get("community", HOME_COMMUNITY) != key:
            continue
        title = chunk.get("document_short") or chunk.get("document")
        if title and title not in titles:
            titles.append(title)
    return titles


def answerable() -> list[Community]:
    """The communities a resident can actually be answered from, in order.

    Read off the index rather than the registry, so a community appears the
    moment its documents do and disappears if they are removed. Three Lakes is
    declared and holds nothing, and must not be offered as a choice: offering it
    would promise an answer that cannot come.
    """
    have = available()
    return [c for c in COMMUNITIES if c.key in have]


def unavailable(query: str) -> list[Community]:
    """Communities the question names that there are no documents for.

    A caller that gets a non-empty list must say so and stop. Answering from
    anywhere else would be the silent fallback this whole module exists to
    prevent.
    """
    have = available()
    return [c for c in named_communities(query) if c.key not in have]


_lock = threading.Lock()
_vectors: Optional[np.ndarray] = None
_chunks: list[dict] = []
#: community key -> the rows of `_vectors` belonging to it. Built once at load,
#: so scoping a search is a slice rather than a scan.
_rows: dict[str, np.ndarray] = {}


def _load() -> bool:
    global _vectors, _chunks, _rows
    if _vectors is not None:
        return True
    with _lock:
        if _vectors is not None:
            return True
        if not INDEX_PATH.exists():
            logger.warning("[DOCS] no index at %s; the assistant will refuse everything", INDEX_PATH)
            return False
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        chunks = data.get("chunks") or []
        if not chunks:
            return False
        _vectors = np.asarray([c.pop("vector") for c in chunks], dtype=np.float32)
        _chunks = chunks
        _rebuild_rows()
        logger.info("[DOCS] %d chunks loaded, %d dimensions, communities: %s",
                    len(_chunks), _vectors.shape[1],
                    ", ".join(f"{k} ({len(v)})" for k, v in sorted(_rows.items())))
        return True


def _rebuild_rows() -> None:
    """Recompute the per-community row map. Call after the chunks change."""
    global _rows
    rows: dict[str, list[int]] = {}
    for i, chunk in enumerate(_chunks):
        rows.setdefault(chunk.get("community", HOME_COMMUNITY), []).append(i)
    _rows = {key: np.asarray(idx, dtype=np.int32) for key, idx in rows.items()}


def _persist() -> None:
    """Write the index back out, chunks and vectors together.

    Written to a temporary file and moved into place, because a half written
    index read at startup is an assistant that answers from half a document and
    cannot tell that anything is missing.
    """
    payload = {
        "model": "all-MiniLM-L6-v2",
        "dimensions": int(_vectors.shape[1]) if _vectors is not None else 384,
        "chunks": [
            {**chunk, "vector": [round(float(x), 6) for x in _vectors[i]]}
            for i, chunk in enumerate(_chunks)
        ],
    }
    tmp = INDEX_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(INDEX_PATH)


def add_chunks(chunks: list[dict], vectors) -> int:
    """Put a newly uploaded document's sections into the live index.

    In memory first, then on disk, so a resident asking a question a second
    after the upload gets the new document without waiting for a restart. The
    lock matters: two uploads at once would otherwise interleave their appends
    and leave the vectors and the chunks a row apart, which is not an error
    anybody would notice until an answer cited the wrong section.
    """
    global _vectors, _chunks
    if not chunks:
        return 0
    _load()
    with _lock:
        added = np.asarray(vectors, dtype=np.float32)
        _vectors = added if _vectors is None else np.vstack([_vectors, added])
        _chunks = _chunks + list(chunks)
        _rebuild_rows()
        _persist()
    logger.info("[DOCS] %d section(s) added, %d in the index", len(chunks), len(_chunks))
    return len(chunks)


def drop_document(doc_id: str) -> int:
    """Remove every section of one document from the live index.

    The client asked for a document he removes to stop answering immediately,
    which means the in-memory copy has to lose it too. Leaving it until the next
    restart would mean the interface says a document is gone while the assistant
    is still quoting it.
    """
    global _vectors, _chunks
    if not _load():
        return 0
    with _lock:
        keep = [i for i, c in enumerate(_chunks) if c.get("doc_id") != doc_id]
        removed = len(_chunks) - len(keep)
        if not removed:
            return 0
        _chunks = [_chunks[i] for i in keep]
        _vectors = _vectors[np.asarray(keep, dtype=np.int32)] if keep else None
        _rebuild_rows()
        _persist()
    logger.info("[DOCS] %d section(s) of %s removed, %d left", removed, doc_id, len(_chunks))
    return removed


def _embed(query: str) -> Optional[np.ndarray]:
    """The query as a vector, from the model `rag` already holds open.

    Through `rag.embed_text` rather than a SentenceTransformer of our own, and
    that is not a stylistic preference. The first version loaded its own copy,
    which is roughly 90 MB of weights plus torch's allocator on top, and the
    `plumber` service runs under `MemoryMax=700M` and already sits at about
    500 MB. Every question failed with "embedding model unavailable" on the live
    box while passing in the test suite, because pytest runs outside the cgroup
    and without the rest of the app loaded.

    The index was built with the same model and `normalize_embeddings=True`, so
    the vectors are directly comparable and a dot product is the cosine.
    """
    from app.services import rag

    try:
        return np.asarray(rag.embed_text(query), dtype=np.float32)
    except Exception:  # noqa: BLE001 - a missing model must not 500 the route
        logger.exception("[DOCS] embedding model unavailable")
        return None


def ready() -> bool:
    return _load()


def scope(query: str) -> set[str]:
    """Which communities this question may be answered from.

    Naming a community *scopes to* it rather than adding it to home. That is the
    change the client's screenshots asked for: the old behaviour searched
    Serenity plus the named place together, and since the Lauderdale handbook is
    ninety three chunks against Serenity's ninety six, naming Lauderdale was
    enough for its ordinances to fill the top four and push the Serenity answer
    out. Name a place, get that place. Name nothing, get home.
    """
    named = {c.key for c in named_communities(query)}
    return named or {HOME_COMMUNITY}


def _without_community(query: str, named: list[Community]) -> str:
    """The question with the community's name taken out, for embedding only.

    Inside a scoped search the name is pure noise. Every chunk being scored
    already belongs to that community, so "lauderdale" cannot separate them, and
    what it does instead is pull the ranking towards whichever passages happen to
    say the word: "DUTIES AND POWERS of lauderdale lake" put the mission
    statement top at 0.619 and never returned the section it named. Take the name
    out and the same query puts "Duties And Powers" top at 0.518, with the
    runner up at 0.275.

    Scoping has already used the name. This is the second half of that: use it
    once, for what it decides, then stop letting it vote.
    """
    out = query
    for community in named:
        for alias in sorted(community.aliases, key=len, reverse=True):
            words = []
            for word in alias.split():
                if len(word) > 3 and word.endswith("s"):
                    word = word[:-1]
                words.append(re.escape(word) + "s?")
            out = re.sub(r"\b" + r"\s+".join(words) + r"\b", " ", out, flags=re.IGNORECASE)
    # A dangling "in" or "of" left where the name was helps nothing.
    out = re.sub(r"\b(in|at|for|of|from|about|the)\s*$", " ", out.strip(), flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out).strip(" ,.-")
    # "Lauderdale Lakes" on its own is a real question, and stripping it leaves
    # nothing to search for. Keep the original in that case.
    return out if len(out) >= 3 else query


def search(query: str, k: int = 4, chosen: str | None = None) -> list[dict]:
    """The k passages closest to the question, best first, above MIN_SCORE.

    Returns an empty list when nothing clears the floor, and the caller treats
    that as "the documents do not answer this" without asking a model anything.
    That is the whole grounding guarantee: no passages, no answer, no chance to
    invent one.

    Scoping happens *before* ranking. Only the rows belonging to the communities
    in scope are scored at all, so a document from somewhere else cannot appear
    in the results however well it matches. Filtering afterwards, which is what
    this did before, let the ranking be decided by chunks that were then thrown
    away, and the resident got four passages where two would have been.
    """
    query = (query or "").strip()
    if len(query) < 3 or not _load():
        return []

    named = named_communities(query)
    # Naming a community in the question still wins: somebody who types
    # "what does Lauderdale Lakes say about bins" is asking for that on purpose,
    # and the credit under the answer says which community it came from. Failing
    # that, the community the resident chose. Failing that, home.
    allowed = {c.key for c in named} or ({chosen} if chosen in _rows else {HOME_COMMUNITY})
    missing = [c.label for c in unavailable(query)]
    if missing:
        # The caller is expected to have checked `unavailable()` and said so.
        # Refusing here as well means no path through this module can answer a
        # question about one community out of another one's documents.
        logger.info("[DOCS] %r names %s, which has no documents; no search run",
                    query[:60], ", ".join(missing))
        return []

    rows = np.concatenate([_rows[key] for key in sorted(allowed) if key in _rows]) \
        if any(key in _rows for key in allowed) else None
    if rows is None or rows.size == 0:
        return []

    vec = _embed(_without_community(query, named))
    if vec is None:
        return []

    scores = _vectors[rows] @ vec
    order = np.argsort(-scores)[: max(k, 1)]
    hits = [
        {**_chunks[int(rows[j])], "score": round(float(scores[j]), 4)}
        for j in order
        if scores[j] >= MIN_SCORE
    ]
    logger.info(
        "[DOCS] %r -> %d hit(s) of %d in scope, best %.3f, scope=%s",
        query[:60], len(hits), rows.size,
        float(scores[order[0]]) if order.size else 0.0,
        ",".join(sorted(allowed)),
    )
    return hits
