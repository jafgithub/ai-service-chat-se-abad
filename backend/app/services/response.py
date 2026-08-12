"""
Deterministic reply composition.

Everything the customer reads for a search or a booking is built here rather
than by a model, so the numbers always match what "item N" resolves to and
confirmations are exact. With SMART_REPLIES on this is the reply, not a
fallback: the model used to be handed the finished list purely to restate it,
which cost a measured 4.1 s per search. The model is now only used for small
talk (see ``ai.py``).

No em dashes anywhere: the client reads them as machine written, and these
strings go straight to customers.
"""

from typing import Optional


def build_shown(services: list[dict]) -> list[dict]:
    """The compact numbered list persisted on the session for reference resolution."""
    shown = []
    for i, p in enumerate(services, 1):
        shown.append({
            "position": i,
            "id": p["id"],
            "name": p["name"],
            "price": p.get("price_per_unit"),
            "unit": p.get("unit", "unit"),
        })
    return shown


def numbered_list(services: list[dict], limit: int = 5) -> str:
    lines = []
    for i, p in enumerate(services[:limit], 1):
        price = p.get("price_per_unit")
        price_str = f"${float(price):.2f}" if price is not None else ""
        lines.append(f"{i}. {p['name']}: {price_str}/{p.get('unit', 'unit')}".rstrip("/"))
    return "\n".join(lines)


def search_reply(services: list[dict]) -> str:
    if not services:
        return ("I couldn't find anything matching that. Try a different keyword, "
                "or tell me what is happening. Leaks, blocked drains, boilers and bathrooms "
                "are the usual ones.")
    intro = "Here are the best matches:" if len(services) > 1 else "Here's what I found:"
    tail = "\n\nSay \"book item 2\" (or any number) and I will show you the next available times."
    return f"{intro}\n{numbered_list(services)}{tail}"


def added_reply(added: list[tuple[str, int]]) -> str:
    if not added:
        return ("I'm not sure which item you meant. Tell me the number from the list "
                "(e.g. \"add item 2\") or the service name.")
    parts = ", ".join(f"{qty} x {name}" if qty > 1 else name for name, qty in added)
    return f"Added {parts} to your cart. Anything else I can help you with?"


def removed_reply(name: Optional[str]) -> str:
    if not name:
        return "I couldn't find that item in your cart. Which one would you like to remove?"
    return f"Removed {name} from your cart. Anything else I can help you with?"


def quantity_reply(name: Optional[str], qty: int) -> str:
    if not name:
        return "Tell me which item and the new quantity, e.g. \"change item 2 to 3\"."
    if qty <= 0:
        return f"Removed {name} from your cart. Anything else?"
    return f"Updated {name} to {qty}. Anything else I can help you with?"


def cart_reply(cart: dict) -> str:
    if not cart["items"]:
        return "Your cart is empty right now. What would you like to add?"
    lines = [f"{i}. {li['name']} x {li['quantity']}: ${li['subtotal']:.2f}"
             for i, li in enumerate(cart["items"], 1)]
    return "Here's your cart:\n" + "\n".join(lines) + f"\nTotal: ${cart['total']:.2f}\n\nSay \"checkout\" when you're ready."


def checkout_reply(cart: dict) -> str:
    if not cart["items"]:
        return "Your cart is empty. Add a few items first, then say \"checkout\"."
    return f"Great! Your cart total is ${cart['total']:.2f}. I'll take you to checkout to confirm your details."
