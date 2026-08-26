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
    """The shortlist, numbered so "book item 2" resolves.

    Two things this deliberately does not say. There is no "/unit": a visit is
    not sold by the kilo, and the catalogue's unit column is the placeholder
    string "unit" on every single row. And the figure is prefixed with "from",
    because it is the service's guide price and every provider sets their own;
    quoting it flat and then showing a different number on the review screen is
    how a booking flow loses somebody two steps before it takes their money.
    """
    lines = []
    for i, p in enumerate(services[:limit], 1):
        price = p.get("price_per_unit")
        price_str = f": from ${float(price):.2f}" if price else ""
        lines.append(f"{i}. {p['name']}{price_str}")
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
    """Choosing a service, which used to be adding it to a cart.

    The intent engine still calls this "add", and one line below is why that is
    left alone: what the customer said is "book item 2", and what they want next
    is to see who can do it. So the reply hands over to the provider list rather
    than confirming a basket. Nothing here quotes a price, because the price is
    the provider's and is not known yet.
    """
    if not added:
        return ("I'm not sure which one you meant. Tell me the number from the list "
                "(e.g. \"book item 2\") or the name of the service.")
    name = added[0][0]
    return f"Right, {name}. Here is who can do that, and when they are free."


def removed_reply(name: Optional[str]) -> str:
    if not name:
        return "Nothing is chosen at the moment. Tell me what has gone wrong and I will look it up."
    return f"Fine, I have set {name} aside. What else can I help with?"


def quantity_reply(name: Optional[str], qty: int) -> str:
    """A visit is not a quantity.

    Somebody who says "change item 2 to 3" is thinking in a shop, so the reply
    says plainly that this is not one, and points at the thing that does vary:
    how long the visit is and when it happens.
    """
    if not name:
        return "Tell me which one you mean by its number, e.g. \"book item 2\"."
    return (f"One visit covers {name}. If it is a bigger job than that, "
            "say so and I will find someone with a longer slot.")


def cart_reply(cart: dict) -> str:
    """What they have picked so far. Deliberately no total.

    Whatever the shop's cart is holding, the price of the work is the chosen
    provider's, and no provider has been chosen at this point. Quoting a figure
    here would be quoting the guide price as though it were a quote.
    """
    if not cart["items"]:
        return "You have not picked anything yet. What do you need doing?"
    lines = [f"{i}. {li['name']}" for i, li in enumerate(cart["items"], 1)]
    return ("So far you are looking at:\n" + "\n".join(lines) +
            "\n\nSay \"book item 1\" and I will show you who can do it and when.")


def documents_reply(documents: list[dict]) -> str:
    """What to say above the documents themselves.

    Short on purpose. The links are underneath and they carry the titles, so
    repeating every name here would say the same thing twice on a small screen.
    Whether a document can be *answered from* is worth a word though: a resident
    who downloads a site map and then asks a question about it should not be
    surprised by the refusal.
    """
    if not documents:
        return "I could not find a document by that name."

    if len(documents) == 1:
        doc = documents[0]
        line = f"Here is the {doc['title']}."
        if not doc["answerable"]:
            line += " It is a scan, so I can give you the file but I cannot answer questions from it."
        return line

    return f"I found {len(documents)} documents that match. Here they are."


def shelf_reply(community: str, documents: list[dict]) -> str:
    """Everything one community holds, in answer to "what have you got".

    Counted rather than listed, because the list is directly underneath. The
    count is the part that is not obvious from looking: an association holding
    one colour sheet is a different proposition from one holding six, and a
    resident deserves to know which they are dealing with.
    """
    if not documents:
        return f"I do not hold anything for {community} yet."
    if len(documents) == 1:
        return f"{community} has one document loaded. Here it is."
    return f"Here is everything I hold for {community}, {len(documents)} documents."


def checkout_reply(cart: dict) -> str:
    if not cart["items"]:
        return "Tell me what needs doing first and I will find someone who does it."
    name = cart["items"][0]["name"]
    return f"Let's get {name} booked. Pick a provider and a time and I will confirm it."
