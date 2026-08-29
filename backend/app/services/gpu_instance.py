"""
Starting, stopping and finding our GPU.

The service assistant runs on Lightsail, which carries an AWS managed role and
cannot be given a custom IAM instance profile. So there is no role to assume:
this uses a dedicated IAM user whose key is in .env and whose policy permits
start and stop on exactly one instance ARN and nothing else.

Two things here are load bearing.

**The address is read from the API, never configured.** A stopped EC2 instance
loses its public address and gets a different one when it starts again, so
anything written into .env would be correct once and wrong forever after. An
Elastic IP would fix it and costs about $3.60 a month to sit attached to a
stopped machine, which quietly undoes a good part of what the auto-off saves.
DescribeInstances returns the current address in the same call that returns the
state, so asking is free.

**The health probe never sits on a resident's request path.** `llm.generate`
reads the cache and never blocks; if the cache says not ready it goes straight
to Gemini. What refreshes the cache is the admin panel's own polling, which is
running exactly when somebody is watching the thing start up.

Nothing here raises. Every function returns a dict, and an unreachable AWS is
reported as a state of "unknown" rather than as a 500 on the admin page.
"""

import logging
import time
from typing import Any

from app.core.config import settings
from app.services import ollama_service

logger = logging.getLogger("ai")

OLLAMA_PORT = 11434

#: How long a health reading stays good. Short, because it is what decides
#: whether a question goes to the GPU, and the cost of being wrong is one
#: unnecessary Gemini answer.
HEALTH_TTL_SECONDS = 15

_health: dict[str, Any] = {"ready": False, "checked_at": 0.0, "reason": "not checked yet"}
_last: dict[str, Any] = {}


def is_configured() -> bool:
    return bool(settings.GPU_INSTANCE_ID
                and settings.AWS_ACCESS_KEY_ID
                and settings.AWS_SECRET_ACCESS_KEY)


def _client():
    """Built per call, so a key rotated in .env needs no restart."""
    import boto3
    return boto3.client(
        "ec2",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def state() -> dict:
    """What the instance is doing, and where it is.

    Returns {"state", "ip", "since", "error"}. `state` is one of AWS's own
    words (pending, running, stopping, stopped, ...) or "not-configured" when
    there is no instance to ask about, or "unknown" when AWS could not be
    reached.
    """
    if not is_configured():
        return {"state": "not-configured", "ip": None, "since": None, "error": ""}

    try:
        data = _client().describe_instances(InstanceIds=[settings.GPU_INSTANCE_ID])
    except Exception as exc:  # noqa: BLE001 - the admin page must still render
        logger.warning("[GPU] describe failed: %s", type(exc).__name__)
        return {"state": "unknown", "ip": None, "since": None,
                "error": f"Could not reach AWS ({type(exc).__name__})."}

    try:
        instance = data["Reservations"][0]["Instances"][0]
    except (KeyError, IndexError):
        return {"state": "unknown", "ip": None, "since": None,
                "error": "AWS returned no such instance."}

    found = {
        "state": instance["State"]["Name"],
        "ip": instance.get("PublicIpAddress"),
        # For a running instance this is when it was last started, which is what
        # the panel needs to say how long it has been up.
        "since": instance.get("LaunchTime").isoformat() if instance.get("LaunchTime") else None,
        "error": "",
    }
    _last.update(found)
    return found


def endpoint() -> str:
    """Where Ollama is, or "" if there is nowhere to send anything.

    Uses the address from the last describe rather than making another call:
    this runs on the request path, and the panel's polling keeps it fresh.
    """
    if settings.OLLAMA_URL:
        return settings.OLLAMA_URL.rstrip("/")
    ip = _last.get("ip")
    return f"http://{ip}:{OLLAMA_PORT}" if ip else ""


def health(max_age: int = HEALTH_TTL_SECONDS) -> dict:
    """Can a question go to the GPU right now?

    Cached. Pass max_age=0 to force a fresh reading, which is what the admin
    status endpoint does and what keeps this warm for everybody else.
    """
    age = time.time() - _health["checked_at"]
    if age < max_age:
        return dict(_health)

    if not is_configured():
        return _record(False, "The GPU is not set up yet.")

    now = state()
    if now["state"] != "running":
        return _record(False, f"The GPU is {now['state']}.")

    base = endpoint()
    if not base:
        return _record(False, "The GPU is running but has no address yet.")

    if not ollama_service.is_up(base):
        # Normal for a minute or two after the instance reaches "running": the
        # machine is up before Ollama is.
        return _record(False, "The GPU is running but not answering yet.")

    return _record(True, "")


def _record(ready: bool, reason: str) -> dict:
    _health.update({"ready": ready, "checked_at": time.time(), "reason": reason})
    return dict(_health)


def start() -> dict:
    return _change("start")


def stop() -> dict:
    return _change("stop")


def _change(action: str) -> dict:
    if not is_configured():
        return {"ok": False, "error": "The GPU is not set up yet.", **state()}

    try:
        call = getattr(_client(), f"{action}_instances")
        call(InstanceIds=[settings.GPU_INSTANCE_ID])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[GPU] %s failed: %s", action, type(exc).__name__)
        return {"ok": False, "error": f"Could not {action} the GPU ({type(exc).__name__}).",
                **state()}

    logger.info("[GPU] %s requested for %s", action, settings.GPU_INSTANCE_ID)
    # Stale by definition: AWS reports "pending"/"stopping" for a while. The
    # panel polls, so the truth arrives a few seconds later either way.
    _record(False, f"The GPU is {action}ing.")
    return {"ok": True, "error": "", **state()}
