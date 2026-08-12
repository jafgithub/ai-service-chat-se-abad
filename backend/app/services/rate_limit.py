"""Slowing down somebody guessing passwords.

Login was unthrottled, which meant an attacker could try a password list against
a known email as fast as the network allowed. PBKDF2 at 480,000 iterations makes
each attempt cost us about a tenth of a second, so it is not free for them
either, but "expensive" is not "prevented" and the cost lands on our server.

Deliberately in memory rather than Redis. Adding a second service to a 1.9 GB
box that already holds an embedding model, to defend one endpoint, is a poor
trade. What that costs is honest and worth writing down:

* **It is per process.** Run two workers and the effective limit doubles. This
  runs a single uvicorn worker today, and the limit is loose enough that the
  doubling would still be a limit.
* **It is forgotten on restart.** An attacker who could restart the service has
  already won.
* **It is per address**, so a botnet spreads across it. It stops the common
  case, which is one machine grinding through a list.

Two counters, because they answer different questions. One per address, which
catches somebody spraying many accounts. One per email, which catches somebody
grinding one account from several addresses.

If this ever needs to survive a restart or span processes, the shape is already
right: replace the dictionaries with the same two keys in Redis.
"""

import logging
import threading
import time
from collections import defaultdict, deque

logger = logging.getLogger("auth")

#: Generous on purpose. A person who has forgotten which password they used will
#: try a handful; nobody legitimate tries fifty.
MAX_PER_EMAIL = 8
MAX_PER_ADDRESS = 20
WINDOW_SECONDS = 15 * 60

#: A sliding window keeps the memory bounded by attempts rather than by time,
#: and old entries fall off as they are read.
_attempts: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()

#: Stops a long-running process accumulating a key per address it has ever seen.
_last_sweep = 0.0
_SWEEP_EVERY = 300


def _prune(key: str, now: float) -> deque:
    window = _attempts[key]
    cutoff = now - WINDOW_SECONDS
    while window and window[0] < cutoff:
        window.popleft()
    return window


def _sweep(now: float) -> None:
    global _last_sweep
    if now - _last_sweep < _SWEEP_EVERY:
        return
    _last_sweep = now
    cutoff = now - WINDOW_SECONDS
    for key in [k for k, w in _attempts.items() if not w or w[-1] < cutoff]:
        _attempts.pop(key, None)


def check(email: str, address: str) -> int | None:
    """Seconds to wait, or None when the attempt may proceed.

    Read only: an attempt is not counted until it fails, so somebody typing
    their password correctly ten times in a row is never locked out.
    """
    now = time.time()
    with _lock:
        _sweep(now)
        for key, limit in ((f"e:{email.lower()}", MAX_PER_EMAIL),
                           (f"a:{address}", MAX_PER_ADDRESS)):
            window = _prune(key, now)
            if len(window) >= limit:
                wait = int(WINDOW_SECONDS - (now - window[0])) + 1
                logger.warning(
                    f"[AUTH] rate limited {key.split(':', 1)[0]} after "
                    f"{len(window)} failures; {wait}s to wait"
                )
                return max(wait, 1)
    return None


def record_failure(email: str, address: str) -> None:
    """Count a failed attempt against both the email and the address."""
    now = time.time()
    with _lock:
        _attempts[f"e:{email.lower()}"].append(now)
        _attempts[f"a:{address}"].append(now)


def clear(email: str, address: str) -> None:
    """Forget the failures after a success, so one bad guess before the right
    password does not count towards a later lockout."""
    with _lock:
        _attempts.pop(f"e:{email.lower()}", None)
        _attempts.pop(f"a:{address}", None)


def reset() -> None:
    """For tests. Nothing in the application calls this."""
    with _lock:
        _attempts.clear()
