"""
Deterministic intent parsing + reference resolution.

The LLM stays in a phrasing-only role. This module decides what the user
actually wants — search / add / remove / set-quantity / view cart / checkout —
and resolves references like "item 2", "the cheapest", "it", or a bare service
name to a concrete catalog item. Being rule-based makes "book item 2"
100% reliable rather than dependent on the model.

`last_shown_json` on the session is the numbered list from the most recent
search; positions in it are what "item N" / ordinals point at.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("intent")

# ── Vocab ────────────────────────────────────────────────────────────────────
ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
# Positions may arrive spelled out: speech-to-text writes "add item two", not
# "add item 2". "a"/"an" are deliberately left out, because "add an item" names
# no position at all.
SPOKEN_NUMBERS = {w: n for w, n in NUMBER_WORDS.items() if w not in ("a", "an")}

# One "closing" phrase. The full matcher below allows several of these chained
# together ("that's all, thank you!") so compound farewells still resolve.
_CONV_CHUNK = (
    r"(that'?s?\s*(pretty\s*much|all|it|enough|fine|good|great|perfect)(\s+for\s+me)?|"
    r"(it'?s?\s*)?(pretty\s*much|all\s*good|enough)(\s+for\s+me)?|"
    r"no\s*(thanks?|thank\s*you)?|nothing\s*else|i'?m?\s*done|all\s*good|"
    r"thank\s*you|thanks|bye|goodbye|see\s*you|have\s*a\s*(good|great|nice)(\s+day)?|"
    r"ok(ay)?|sure|cool|sounds\s*good|nope|nah|great|perfect|awesome|"
    r"that\s*(will\s*be\s*)?all|i'?m?\s*good|good\s*enough)"
)
_CONVERSATIONAL = re.compile(
    r"^\s*" + _CONV_CHUNK + r"(\s*[,.!;]+\s*" + _CONV_CHUNK + r")*\s*[.!,]*\s*$",
    re.IGNORECASE,
)
_VIEW_CART = re.compile(r"\b(view|show|see|what'?s?\s+in|check)\b.*\bcart\b|\bmy\s+cart\b|\bcart\s+total\b", re.IGNORECASE)
_CHECKOUT = re.compile(
    r"\b(check\s*out|checkout|confirm\s+(my\s+)?(booking|appointment)|"
    r"book\s+(it|that|this)|that\s+time\s+works|"
    r"place\s+(my\s+)?order|confirm\s+(my\s+)?order|proceed\s+to\s+(checkout|payment))\b",
    re.IGNORECASE,
)
# A customer books rather than buys, so the verbs differ. "add" is kept because
# people say it anyway, and because the intent rules are the thing that has to
# understand what somebody said rather than what they ought to have said.
_ADD = re.compile(
    r"\b(book|schedule|arrange|reserve|"
    r"add|put|include|"
    r"i'?ll?\s+(take|have|book)|i\s+want\s+to\s+(book|arrange)|"
    r"send\s+(someone|somebody)|come\s+(out|round)|get\s+me)\b",
    re.IGNORECASE,
)
_REMOVE = re.compile(r"\b(remove|delete|take\s+out|drop|get\s+rid\s+of|take\s+off)\b", re.IGNORECASE)
_SET_QTY = re.compile(r"\b(change|make|set|update)\b.*\b(to|quantity|qty)\b", re.IGNORECASE)
_CHEAPEST = re.compile(r"\b(cheapest|lowest\s+price|least\s+expensive|most\s+affordable|best\s+deal)\b", re.IGNORECASE)
_PRONOUN = re.compile(r"\b(it|that|this|that\s+one|this\s+one|the\s+same)\b", re.IGNORECASE)
# "item 2", "number 2", "no 2", "option 3", and the spoken "item two"
_ITEM_NUM = re.compile(
    r"\b(?:item|option|number|no\.?)\s*#?\s*(\d{1,2}|"
    + "|".join(sorted(SPOKEN_NUMBERS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
# bare "#2" / "# 2" (no word boundary before '#')
_HASH_NUM = re.compile(r"#\s*(\d{1,2})\b")
_ORDINAL = re.compile(r"\b(" + "|".join(ORDINALS) + r")\b", re.IGNORECASE)


@dataclass
class Ref:
    item_id: int
    name: str
    quantity: int = 1


@dataclass
class Intent:
    type: str                      # search | add_to_cart | remove_from_cart | set_quantity | view_cart | checkout | conversational
    refs: list[Ref] = field(default_factory=list)
    quantity: int = 1              # for set_quantity
    query: str = ""                # for search
    unresolved: bool = False       # a cart action was intended but no service could be resolved


def _last_shown(session) -> list[dict]:
    return session.last_shown_json or []


def _as_position(token: str) -> Optional[int]:
    """'2' and 'two' both mean 2; anything else means no position."""
    return int(token) if token.isdigit() else SPOKEN_NUMBERS.get(token.lower())


def _positions(text: str) -> list[int]:
    """Every numbered/ordinal position referenced in the text, in order."""
    positions: list[int] = []
    for m in _ITEM_NUM.finditer(text):
        if (pos := _as_position(m.group(1))) is not None:
            positions.append(pos)
    for m in _HASH_NUM.finditer(text):
        positions.append(int(m.group(1)))
    for m in _ORDINAL.finditer(text):
        positions.append(ORDINALS[m.group(1).lower()])
    # de-dupe, keep order
    seen: set[int] = set()
    out: list[int] = []
    for p in positions:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _quantity_for(text: str, near: str) -> int:
    """Best-effort quantity: '2 of item 3', 'add three item 2', '3x item 2'."""
    m = re.search(r"(\d{1,2})\s*(?:x|of|×)?\s*" + re.escape(near), text, re.IGNORECASE)
    if m:
        return max(1, int(m.group(1)))
    for word, val in NUMBER_WORDS.items():
        if re.search(r"\b" + word + r"\b\s+(?:of\s+)?" + re.escape(near), text, re.IGNORECASE):
            return val
    m = re.search(r"\bx\s*(\d{1,2})\b", text, re.IGNORECASE)
    if m:
        return max(1, int(m.group(1)))
    return 1


def _resolve_by_position(pos: int, shown: list[dict]) -> Optional[dict]:
    for row in shown:
        if int(row.get("position", -1)) == pos:
            return row
    if 1 <= pos <= len(shown):        # fall back to list order
        return shown[pos - 1]
    return None


def _resolve_name(query: str, db: "Session") -> Optional[dict]:
    """Resolve a bare service name via a top-1 RAG search (for 'add milk')."""
    from app.services import rag  # lazy: keeps the ML stack out of import time

    cleaned = re.sub(
        r"\b(add|put|include|remove|delete|take\s+out|to|from|my|the|cart|please|a|an|some|of|to\s+cart)\b",
        " ", query, flags=re.IGNORECASE,
    ).strip()
    if len(cleaned) < 2:
        return None
    results = rag.search_products(query=cleaned, db=db, top_k=1)
    if results:
        r = results[0]
        return {"id": r["id"], "name": r["name"], "price": r.get("price_per_unit")}
    return None


def _build_refs(text: str, session, db: "Session", allow_name: bool) -> list[Ref]:
    shown = _last_shown(session)
    refs: list[Ref] = []

    # 1) explicit positions / ordinals
    positions = _positions(text)
    for pos in positions:
        row = _resolve_by_position(pos, shown)
        if row:
            qty = _quantity_for(text, f"item {pos}") or _quantity_for(text, str(pos))
            refs.append(Ref(item_id=int(row["id"]), name=row["name"], quantity=qty))
    if refs:
        return refs

    # 2) "the cheapest" from the shown list
    if _CHEAPEST.search(text) and shown:
        row = min(shown, key=lambda r: float(r.get("price") or 0))
        return [Ref(item_id=int(row["id"]), name=row["name"], quantity=_quantity_for(text, row["name"]))]

    # 3) pronoun → last referenced / the only shown item
    if _PRONOUN.search(text):
        if session.last_referenced_item_id:
            name = next((r["name"] for r in shown if int(r["id"]) == int(session.last_referenced_item_id)), "that item")
            return [Ref(item_id=int(session.last_referenced_item_id), name=name)]
        if len(shown) == 1:
            return [Ref(item_id=int(shown[0]["id"]), name=shown[0]["name"])]

    # 4) bare service name (only for add/remove verbs)
    if allow_name:
        row = _resolve_name(text, db)
        if row:
            return [Ref(item_id=int(row["id"]), name=row["name"], quantity=_quantity_for(text, row["name"]))]

    return refs


def parse(message: str, session, db: "Session") -> Intent:
    text = (message or "").strip()

    if _CONVERSATIONAL.match(text):
        return Intent(type="conversational")
    if _CHECKOUT.search(text):
        return Intent(type="checkout")

    # Cart-mutation verbs are checked before view_cart, because "add milk to my
    # cart" / "remove item 2 from my cart" also contain the words "my cart".
    if _SET_QTY.search(text):
        refs = _build_refs(text, session, db, allow_name=True)
        m = re.search(r"\bto\s+(\d{1,2})\b", text, re.IGNORECASE)
        qty = int(m.group(1)) if m else 1
        if refs:
            return Intent(type="set_quantity", refs=refs[:1], quantity=qty)
        return Intent(type="set_quantity", unresolved=True)

    if _REMOVE.search(text):
        refs = _build_refs(text, session, db, allow_name=True)
        return Intent(type="remove_from_cart", refs=refs, unresolved=not refs)

    if _ADD.search(text):
        refs = _build_refs(text, session, db, allow_name=True)
        return Intent(type="add_to_cart", refs=refs, unresolved=not refs)

    if _VIEW_CART.search(text):
        return Intent(type="view_cart")

    # No cart verb but a plain "item 2" right after a list → treat as add.
    if _positions(text) and _last_shown(session):
        refs = _build_refs(text, session, db, allow_name=False)
        if refs:
            return Intent(type="add_to_cart", refs=refs)

    return Intent(type="search", query=text)
