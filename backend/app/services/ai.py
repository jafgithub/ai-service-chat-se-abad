"""
LLM phrasing (OpenAI gpt-4o-mini).

The model no longer decides actions — the deterministic intent parser and cart
service do that. Here the model only makes replies sound friendly. Every call
degrades gracefully: if OpenAI is unavailable (no key, quota, network) the
caller falls back to the deterministic text in ``response.py`` so the assistant
keeps working end-to-end.
"""

import logging
import time
from typing import Optional

from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger("ai")

client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

SEARCH_SYSTEM = """You are a calm, practical booking assistant for {shop_name}, a local plumbing firm.
You are given a numbered list of real services this firm offers that matched what the customer described.

Write a SHORT reply that:
- presents the services as a numbered list in the EXACT order given, starting at 1, one per line, as "N. Name, from $price".
- after the list, tell the customer they can say "book item 2" (using the number) and you will show them the next available times.
Rules: use ONLY the services given. Never invent a service, a price or a time. Never promise
that somebody can attend today unless the customer is told the available times. If the problem
sounds like an emergency, say the firm should be called rather than booked. No markdown symbols
or asterisks, plain text only.
"""

SMALLTALK_SYSTEM = """You are a warm, concise booking assistant for {shop_name}, a local plumbing firm.
Reply in ONE short sentence, plain text only (no markdown).
- If the customer is greeting you, welcome them and ask what they're looking for.
- If they are saying thanks / goodbye / that's all, thank them warmly and wish them a great day.
"""


def _complete(system: str, user: str, max_tokens: int = 300) -> Optional[str]:
    # Gemini path (local demo). Returns None on failure → deterministic fallback.
    if settings.LLM_PROVIDER == "gemini":
        from app.services import gemini_service
        return gemini_service.generate(system, user, max_tokens=max_tokens)

    if client is None:
        return None
    try:
        t0 = time.perf_counter()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.4,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        elapsed = (time.perf_counter() - t0) * 1000
        reply = (response.choices[0].message.content or "").strip()
        logger.info(f"[AI] gpt-4o-mini reply in {elapsed:.0f}ms ({len(reply)} chars)")
        return reply or None
    except Exception as exc:  # noqa: BLE001 - any failure means fall back to deterministic text
        logger.warning(f"[AI] OpenAI call failed ({type(exc).__name__}); falling back to deterministic reply")
        return None


def search_intro(user_message: str, services: list[dict], shop_name: str = "Plumber Assistant") -> Optional[str]:
    """LLM-phrased search reply (numbered list). Returns None on any failure."""
    if not services:
        return None
    block = "\n".join(
        f"{i}. {p['name']} | ${float(p['price_per_unit']):.2f}/{p.get('unit', 'unit')}"
        for i, p in enumerate(services[:5], 1)
    )
    user = f"Customer message: {user_message}\n\nProducts (in order):\n{block}"
    return _complete(SEARCH_SYSTEM.format(shop_name=shop_name), user)


def small_talk(user_message: str, shop_name: str = "Plumber Assistant") -> Optional[str]:
    """LLM-phrased greeting/farewell. Returns None on any failure."""
    return _complete(SMALLTALK_SYSTEM.format(shop_name=shop_name), f"Customer message: {user_message}", max_tokens=80)
