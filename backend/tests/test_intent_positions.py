"""Position references in a message: "item 2", "item two", "the second one".

These matter most for voice. Speech-to-text spells numbers out, so a shopper
saying "add item two" reaches the parser as a word. Before that was handled the
phrase fell through to a name search and added a product called "The Mad Wife
Item" instead of the second item on the list.
"""

import pytest

from app.services.intent import _positions


@pytest.mark.parametrize(
    "text, expected",
    [
        # digits, as typed
        ("add item 2 to my cart", [2]),
        ("option 3", [3]),
        ("number 10 please", [10]),
        ("#4", [4]),
        # spelled out, as spoken
        ("Add item two to my cart.", [2]),
        ("add item ten", [10]),
        ("option seven please", [7]),
        ("number three", [3]),
        # ordinals
        ("add the second one", [2]),
        ("the first please", [1]),
        # several, in the order they appear, de-duplicated
        ("add number three and item 5", [3, 5]),
        ("item 2 and item two", [2]),
    ],
)
def test_positions_found(text, expected):
    assert _positions(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "add an item",                    # "an" is an article, not position 1
        "add a item to my cart",          # likewise "a"
        "add two milk",                   # a quantity, no position word before it
        "i want three bottles of water",  # quantity again
        "show me milk",
        "",
    ],
)
def test_no_position_found(text):
    assert _positions(text) == []
