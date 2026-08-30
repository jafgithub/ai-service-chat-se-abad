"""Switching between Gemini and our own GPU, and what happens when it is off.

The rule every test here circles: a resident must never see a broken assistant
because a machine was booting, and the admin page must never claim the GPU
answered when Gemini did. Those two together are the whole feature.

Nothing here touches AWS or a GPU. `gpu_instance.health` is the seam, and it is
patched, because the question being tested is what the router does with the
answer rather than how the answer is obtained.
"""

import json

import httpx
import pytest

from app.core.config import settings
from app.services import ai_runtime, gemini_service, llm, ollama_service


@pytest.fixture
def switch(tmp_path, monkeypatch):
    """A runtime switch in a temporary file, starting on Gemini."""
    path = tmp_path / "ai_runtime.json"
    monkeypatch.setattr(ai_runtime, "RUNTIME_PATH", path)
    monkeypatch.setattr(ai_runtime, "_cache", None)
    return path


def on_gpu(monkeypatch, ready: bool, reason: str = "The GPU is stopped."):
    """Pretend the switch says GPU and the hardware is, or is not, there."""
    from app.services import gpu_instance

    monkeypatch.setattr(ai_runtime, "current", lambda: ai_runtime.GPU)
    monkeypatch.setattr(gpu_instance, "health",
                        lambda *a, **k: {"ready": ready, "checked_at": 0.0,
                                         "reason": "" if ready else reason})


# ── the switch itself ────────────────────────────────────────────────────────

def test_a_missing_file_reads_as_gemini(switch):
    """The safe floor. Defaulting to the GPU would mean answering from a machine
    that is almost certainly switched off."""
    assert not switch.exists()
    assert ai_runtime.current() == ai_runtime.GEMINI


def test_a_corrupt_file_reads_as_gemini_rather_than_taking_the_app_down(switch):
    switch.write_text("{ this is not json", encoding="utf-8")
    assert ai_runtime.current() == ai_runtime.GEMINI


def test_a_file_naming_an_engine_we_do_not_have_reads_as_gemini(switch):
    switch.write_text(json.dumps({"provider": "a-friend-of-mine"}), encoding="utf-8")
    assert ai_runtime.current() == ai_runtime.GEMINI


def test_the_switch_is_picked_up_without_anybody_calling_reload(switch):
    """The reason this is keyed on mtime rather than on an explicit reload: under
    more than one worker, the process that did not serve the POST still has to
    see the change on its very next message."""
    assert ai_runtime.current() == ai_runtime.GEMINI

    ai_runtime.set_provider("gpu")

    assert ai_runtime.current() == ai_runtime.GPU


def test_an_engine_we_do_not_offer_is_refused(switch):
    with pytest.raises(ValueError):
        ai_runtime.set_provider("openai")


# ── the ollama client, which must never raise ────────────────────────────────

def test_ollama_returns_none_when_the_machine_cannot_be_reached(monkeypatch):
    def refuse(*a, **k):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(settings, "OLLAMA_URL", "http://192.0.2.1:11434")
    monkeypatch.setattr(httpx, "post", refuse)

    assert ollama_service.generate("s", "u") is None


def test_ollama_returns_none_on_an_error_status(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://192.0.2.1:11434")
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: httpx.Response(500, text="model not loaded"))

    assert ollama_service.generate("s", "u") is None


def test_ollama_returns_none_on_a_200_carrying_html(monkeypatch):
    """Not theoretical. A stopped instance whose address has been reassigned
    answers with somebody else's web page, and a perfectly good 200 on it."""
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://192.0.2.1:11434")
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: httpx.Response(200, text="<html>hello</html>"))

    assert ollama_service.generate("s", "u") is None


def test_ollama_returns_none_when_there_is_no_address_at_all(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_URL", "")
    monkeypatch.setattr(settings, "GPU_INSTANCE_ID", "")

    assert ollama_service.generate("s", "u") is None


def test_ollama_returns_the_reply(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://192.0.2.1:11434")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(
        200, json={"message": {"content": "  Quiet hours are 10pm to 7am.  "}}))

    assert ollama_service.generate("s", "u") == "Quiet hours are 10pm to 7am."


# ── the router ───────────────────────────────────────────────────────────────

def test_gemini_answers_when_the_switch_says_gemini(monkeypatch, switch):
    monkeypatch.setattr(gemini_service, "generate", lambda *a, **k: "from gemini")

    assert llm.generate("s", "u") == "from gemini"
    assert llm.serving()["served_by"] == "gemini"
    assert llm.serving()["fell_back"] is False


def test_the_gpu_answers_when_it_is_ready(monkeypatch):
    on_gpu(monkeypatch, ready=True)
    monkeypatch.setattr(ollama_service, "generate", lambda *a, **k: "from the gpu")
    monkeypatch.setattr(gemini_service, "generate",
                        lambda *a, **k: pytest.fail("Gemini must not be called"))

    assert llm.generate("s", "u") == "from the gpu"
    assert llm.serving()["served_by"] == "gpu"
    assert llm.serving()["fell_back"] is False


def test_gemini_answers_when_the_switch_says_gpu_but_it_is_off(monkeypatch):
    """The single most important behaviour here. This is what happens in front
    of a client when somebody forgets to press start."""
    on_gpu(monkeypatch, ready=False, reason="The GPU is stopped.")
    monkeypatch.setattr(gemini_service, "generate", lambda *a, **k: "from gemini")
    monkeypatch.setattr(ollama_service, "generate",
                        lambda *a, **k: pytest.fail("must not ask a stopped GPU"))

    assert llm.generate("s", "u") == "from gemini"


def test_the_panel_is_told_it_fell_back_and_why(monkeypatch):
    """Falling back silently would let a demo claim credit for Gemini's work."""
    on_gpu(monkeypatch, ready=False, reason="The GPU is stopped.")
    monkeypatch.setattr(gemini_service, "generate", lambda *a, **k: "from gemini")

    llm.generate("s", "u")

    assert llm.serving()["served_by"] == "gemini"
    assert llm.serving()["fell_back"] is True
    assert "stopped" in llm.serving()["reason"]


def test_a_gpu_that_dies_mid_question_falls_back_rather_than_failing(monkeypatch):
    """Ready a moment ago, gone now. The resident still gets an answer."""
    on_gpu(monkeypatch, ready=True)
    monkeypatch.setattr(ollama_service, "generate", lambda *a, **k: None)
    monkeypatch.setattr(gemini_service, "generate", lambda *a, **k: "from gemini")

    assert llm.generate("s", "u") == "from gemini"
    assert llm.serving()["fell_back"] is True
    assert "mid-question" in llm.serving()["reason"]


def test_nothing_available_returns_none_rather_than_raising(monkeypatch):
    """None is the contract every caller in this codebase already handles: it
    means fall back to the deterministic text."""
    on_gpu(monkeypatch, ready=True)
    monkeypatch.setattr(ollama_service, "generate", lambda *a, **k: None)
    monkeypatch.setattr(gemini_service, "generate", lambda *a, **k: None)

    assert llm.generate("s", "u") is None


# ── an address pointed by hand ───────────────────────────────────────────────
#
# The settings file offers OLLAMA_URL as "a manual override for pointing at a
# box by hand", and the installation guide's section 9 tells somebody to use it
# to test the whole arrangement with no AWS at all. That did not work: health()
# gated readiness on GPU_INSTANCE_ID and an AWS key, so an address set by hand
# reported "the GPU is not set up yet" and every question quietly went to
# Gemini however well Ollama was answering. These four hold that shut.

def test_a_hand_pointed_address_is_ready_when_it_answers(monkeypatch):
    from app.services import gpu_instance, ollama_service

    monkeypatch.setattr(gpu_instance.settings, "OLLAMA_URL", "http://10.0.0.9:11434")
    monkeypatch.setattr(gpu_instance.settings, "GPU_INSTANCE_ID", "")
    monkeypatch.setattr(ollama_service, "is_up", lambda base: True)

    reading = gpu_instance.health(max_age=0)

    assert reading["ready"] is True
    assert reading["reason"] == ""


def test_a_hand_pointed_address_that_is_silent_is_not_ready(monkeypatch):
    from app.services import gpu_instance, ollama_service

    monkeypatch.setattr(gpu_instance.settings, "OLLAMA_URL", "http://10.0.0.9:11434")
    monkeypatch.setattr(gpu_instance.settings, "GPU_INSTANCE_ID", "")
    monkeypatch.setattr(ollama_service, "is_up", lambda base: False)

    reading = gpu_instance.health(max_age=0)

    assert reading["ready"] is False
    # Says which thing is not answering, because "the GPU is not set up" sent
    # somebody looking at AWS for a problem that was on their own machine.
    assert "OLLAMA_URL" in reading["reason"]


def test_a_hand_pointed_address_never_calls_aws(monkeypatch):
    """No instance id and no key, so reaching for boto3 would be a crash rather
    than a fallback."""
    from app.services import gpu_instance, ollama_service

    monkeypatch.setattr(gpu_instance.settings, "OLLAMA_URL", "http://10.0.0.9:11434")
    monkeypatch.setattr(gpu_instance.settings, "GPU_INSTANCE_ID", "")
    monkeypatch.setattr(ollama_service, "is_up", lambda base: True)

    def explode():
        raise AssertionError("a hand pointed address must not describe an instance")

    monkeypatch.setattr(gpu_instance, "_client", explode)

    assert gpu_instance.health(max_age=0)["ready"] is True
    assert gpu_instance.state()["state"] == "manual"


def test_the_panel_does_not_call_a_hand_pointed_address_not_configured(monkeypatch):
    """The word on the panel has to match what is happening. "not-configured"
    beside an engine that is answering is the sentence that gets somebody to
    demonstrate the wrong thing to a room."""
    from app.services import gpu_instance

    monkeypatch.setattr(gpu_instance.settings, "OLLAMA_URL", "http://10.0.0.9:11434")
    monkeypatch.setattr(gpu_instance.settings, "GPU_INSTANCE_ID", "")

    assert gpu_instance.state()["state"] == "manual"
