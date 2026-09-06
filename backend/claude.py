"""Shared Claude client for the analysis pipeline.

One place that knows how to call the model, so the coding pass (function 1) and
the theme-reasoning pass (function 2) behave identically: structured JSON out,
adaptive thinking, per-call effort, usage logged, and a clear failure mode.

Nothing here raises into the pipeline. When the key is missing or the call
fails, callers get None and fall back to the deterministic engine — an analysis
that half-completes is worse than one that completes honestly.
"""
import json
import os
import time

MODEL = "claude-opus-5"
PRICING = {"claude-opus-5": (0.005, 0.025)}     # USD per 1K tokens (in, out)

_state = {"beta_fallbacks": True}               # downgraded if the beta is rejected


class ClaudeUnavailable(Exception):
    """Raised only by callers that require Claude and cannot degrade."""


def configured():
    if os.environ.get("QRIP_LLM", "").lower() in {"off", "0", "false", "local"}:
        return False
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def status():
    """What the UI shows about the reasoning engine."""
    if os.environ.get("QRIP_LLM", "").lower() in {"off", "0", "false", "local"}:
        return {"available": False, "model": None,
                "reason": "QRIP_LLM is set to off, so the local engine is in use."}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"available": False, "model": None,
                "reason": "ANTHROPIC_API_KEY is not set. Coding and theme reasoning "
                          "fall back to the local lexicon engine, which reads words "
                          "rather than context."}
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return {"available": False, "model": None,
                "reason": "The anthropic package is not installed. Run "
                          "`pip install anthropic`."}
    return {"available": True, "model": MODEL, "reason": None}


def _client():
    if not configured():
        return None
    try:
        import anthropic
        return anthropic.Anthropic()
    except Exception:
        return None


def structured(system, prompt, schema, effort="medium", max_tokens=16000,
               on_usage=None, retries=2):
    """One structured-output call. Returns the parsed object, or None.

    effort controls how hard the model thinks; 'medium' is the setting the
    theme-sorting pass uses — enough reasoning to weigh a code against every
    candidate theme, without paying for depth this task does not need.
    """
    client = _client()
    if client is None:
        return None

    request = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "thinking": {"type": "adaptive"},
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        },
        "messages": [{"role": "user", "content": prompt}],
    }

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = _send(client, request)
        except Exception as exc:
            last_error = exc
            if _fatal(exc):
                break
            time.sleep(1.5 * (attempt + 1))
            continue

        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            last_error = RuntimeError("declined: " + str(getattr(details, "category", "")))
            break

        usage = getattr(response, "usage", None)
        if on_usage and usage:
            cost_in, cost_out = PRICING.get(MODEL, (0.0, 0.0))
            on_usage(usage.input_tokens, usage.output_tokens,
                     usage.input_tokens / 1000.0 * cost_in
                     + usage.output_tokens / 1000.0 * cost_out)
        try:
            text = next(block.text for block in response.content
                        if block.type == "text")
            return json.loads(text)
        except (StopIteration, ValueError) as exc:
            last_error = exc
            continue

    if last_error is not None:
        print("[claude] call failed:", str(last_error)[:300])
    return None


def _send(client, request):
    """Prefer the server-side refusal fallback; drop it if the account lacks the beta."""
    if _state["beta_fallbacks"]:
        try:
            with client.beta.messages.stream(
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default", **request) as stream:
                return stream.get_final_message()
        except TypeError:
            _state["beta_fallbacks"] = False
        except Exception as exc:
            if _mentions_beta(exc):
                _state["beta_fallbacks"] = False
            else:
                raise
    with client.messages.stream(**request) as stream:
        return stream.get_final_message()


def _mentions_beta(exc):
    text = str(exc).lower()
    return any(word in text for word in ("beta", "fallback", "unexpected keyword"))


def _fatal(exc):
    """Authentication and request-shape errors will not fix themselves on retry."""
    name = type(exc).__name__
    if name in ("AuthenticationError", "PermissionDeniedError", "NotFoundError"):
        return True
    if name == "BadRequestError":
        return True
    return False


def batched(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]
