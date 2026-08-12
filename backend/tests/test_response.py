"""The replies shoppers actually read.

These used to be a fallback for when the model was unavailable. With
SMART_REPLIES on they are the reply for every search and every cart action, so
they are worth holding to a standard.
"""

import pytest

from app.services import response

PRODUCTS = [
    {"id": 1, "name": "Friendly Farms Skim Milk", "price_per_unit": 2.09, "unit": "unit"},
    {"id": 2, "name": "Whole Milk 1 gal", "price_per_unit": 4.48, "unit": "unit"},
]

CART = {
    "items": [{"name": "Skim Milk", "quantity": 2, "subtotal": 4.18}],
    "total": 4.51,
}

BANNED = {"—": "em dash", "–": "en dash"}


def every_reply() -> list[str]:
    """One of each, including the empty cases, which are easy to forget."""
    return [
        response.search_reply(PRODUCTS),
        response.search_reply([]),
        response.added_reply([("Skim Milk", 2)]),
        response.added_reply([("Skim Milk", 1)]),
        response.added_reply([]),
        response.removed_reply("Skim Milk"),
        response.removed_reply(None),
        response.quantity_reply("Skim Milk", 3),
        response.quantity_reply("Skim Milk", 0),
        response.quantity_reply(None, 1),
        response.cart_reply(CART),
        response.cart_reply({"items": [], "total": 0}),
        response.checkout_reply(CART),
        response.checkout_reply({"items": [], "total": 0}),
    ]


@pytest.mark.parametrize("reply", every_reply())
def test_no_banned_dashes(reply):
    """The client reads em and en dashes as machine written, and these strings
    go straight to shoppers rather than into a document."""
    for char, label in BANNED.items():
        assert char not in reply, f"{label} in: {reply!r}"


@pytest.mark.parametrize("reply", every_reply())
def test_replies_are_not_empty(reply):
    assert reply.strip()


def test_search_reply_numbers_match_the_reference_list():
    """The numbering is what "add item 2" resolves against, so the text and
    build_shown must agree. This is the reason the list is composed in code."""
    shown = response.build_shown(PRODUCTS)
    reply = response.search_reply(PRODUCTS)
    for row in shown:
        assert f"{row['position']}. {row['name']}" in reply


def test_search_reply_shows_prices():
    reply = response.search_reply(PRODUCTS)
    assert "$2.09" in reply and "$4.48" in reply


def test_search_reply_caps_the_visible_list():
    """A search can match thousands; the reply must stay readable."""
    many = [
        {"id": i, "name": f"Product {i}", "price_per_unit": 1.0, "unit": "unit"}
        for i in range(1, 51)
    ]
    reply = response.search_reply(many)
    assert "5. Product 5" in reply
    assert "6. Product 6" not in reply


def test_empty_search_suggests_what_to_do_next():
    reply = response.search_reply([])
    assert "couldn't find" in reply.lower()


def test_cart_reply_totals():
    reply = response.cart_reply(CART)
    assert "$4.51" in reply and "Skim Milk" in reply


def test_single_item_is_not_shown_with_a_quantity():
    """"Added Skim Milk" reads better than "Added 1 x Skim Milk"."""
    assert "1 x" not in response.added_reply([("Skim Milk", 1)])
    assert "2 x" in response.added_reply([("Skim Milk", 2)])


# ── products with no name ────────────────────────────────────────────────────
# One exists in the client's catalog (id 194438). A search for "titanium bicycle
# frame" matched it at 0.369 and the assistant answered "1. : $14.29" with the
# card beside it showing a price and no title.

def test_a_nameless_product_is_dropped_before_the_reply_is_built(monkeypatch):
    """The filter lives in rag.search_products, after both search paths join, so
    the numbered list and the cards are built from the same rows."""
    from app.services import rag

    rows = [
        {"id": 1, "name": "Whole Milk", "price_per_unit": 2.09, "unit": "unit", "similarity": 0.5},
        {"id": 2, "name": "   ",        "price_per_unit": 14.29, "unit": "unit", "similarity": 0.4},
        {"id": 3, "name": "",           "price_per_unit": 9.99,  "unit": "unit", "similarity": 0.4},
    ]
    monkeypatch.setattr(rag, "embed_text", lambda q: [0.0] * 384)
    monkeypatch.setattr(rag.catalog_index, "get", lambda: type(
        "I", (), {"rows": 3, "search": lambda *a, **k: list(rows)}
    )())

    results = rag.search_products("titanium bicycle frame", db=None)

    assert [r["id"] for r in results] == [1], "only the named product survives"


def test_the_numbered_list_never_shows_an_empty_name():
    """Belt and braces: even if one reached here, it would be visible as a gap."""
    from app.services.response import search_reply

    reply = search_reply([
        {"id": 1, "name": "Whole Milk", "price_per_unit": 2.09, "unit": "unit"},
    ])
    assert "1. Whole Milk" in reply
    assert "1. :" not in reply
