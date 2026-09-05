"""Optional Claude-backed interpretation layer.

QRIP ships with a deterministic local engine that needs no network, no API key
and no dependencies — that is the default and it always runs first. If the
official Anthropic SDK is installed (``pip install anthropic``) and
ANTHROPIC_API_KEY is set, the same coded segments are then re-read by Claude,
which replaces the local label / emotion / intent / alternative readings where
it returns valid output. Any failure leaves the local coding in place.

Set QRIP_LLM=off to force the local engine even when a key is present.
"""
import json
import os

import db
from . import lexicons as lx

PRIMARY_MODEL = "claude-opus-5"
SECONDARY_MODEL = "claude-sonnet-5"

# USD per 1K tokens (Claude Opus 5: $5 / $25 per MTok).
PRICING = {
    "claude-opus-5": (0.005, 0.025),
    "claude-sonnet-5": (0.002, 0.010),
}

BATCH_SIZE = 20
MAX_UNITS = int(os.environ.get("QRIP_LLM_MAX_UNITS", "300"))

VALID_EMOTIONS = sorted(list(lx.EMOTIONS) + ["neutral"])
VALID_INTENTS = sorted(lx.INTENTS)

SYSTEM_PROMPT = (
    "You are a qualitative research assistant performing open coding on interview "
    "transcript segments. For each segment return one interpretive code. Stay close "
    "to the participant's own words, never invent content, and record genuine "
    "alternative readings where the segment is ambiguous. Confidence should express "
    "how firmly the segment supports the code, not how confident you feel."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "codes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "label": {"type": "string"},
                    "literal_meaning": {"type": "string"},
                    "emotion": {"type": "string", "enum": VALID_EMOTIONS},
                    "intent": {"type": "string", "enum": VALID_INTENTS},
                    "confidence": {"type": "number"},
                    "alternative_interpretations": {
                        "type": "array", "items": {"type": "string"},
                    },
                },
                "required": ["index", "label", "literal_meaning", "emotion", "intent",
                             "confidence", "alternative_interpretations"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["codes"],
    "additionalProperties": False,
}


def _client():
    if os.environ.get("QRIP_LLM", "").lower() in {"off", "0", "false", "local"}:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        return anthropic.Anthropic()
    except Exception:
        return None


def engine_info() -> dict:
    if _client() is not None:
        cin, cout = PRICING[PRIMARY_MODEL]
        return {
            "provider": "anthropic",
            "primary_model": PRIMARY_MODEL,
            "secondary_model": SECONDARY_MODEL,
            "cost_per_1k_in": cin,
            "cost_per_1k_out": cout,
            "label": "Claude (" + PRIMARY_MODEL + ") over the local pipeline",
        }
    return {
        "provider": "local",
        "primary_model": "qrip-local-v1",
        "secondary_model": "qrip-local-v1-alt",
        "cost_per_1k_in": 0.0,
        "cost_per_1k_out": 0.0,
        "label": "Local deterministic engine (no API key configured)",
    }


def enrich_codes(codes, project, user_id):
    client = _client()
    if client is None or not codes:
        return codes

    project_id = project["id"]
    question = project["research_question"] or "(not stated)"
    methodology = project["methodology"] or "thematic"
    targets = codes[:MAX_UNITS]

    for start in range(0, len(targets), BATCH_SIZE):
        batch = targets[start:start + BATCH_SIZE]
        payload = [{
            "index": i,
            "participant": c["participant_label"],
            "asked": (c.get("question_context") or "")[:200],
            "segment": c["quote_text"][:1200],
        } for i, c in enumerate(batch)]
        prompt = (
            "Research question: " + question + "\n"
            "Methodology: " + methodology + "\n"
            "Emotion must be one of: " + ", ".join(VALID_EMOTIONS) + ".\n"
            "Intent must be one of: " + ", ".join(VALID_INTENTS) + ".\n"
            "Confidence is 0-1. Give 1-3 alternative interpretations per segment.\n"
            "Segments:\n" + json.dumps(payload, ensure_ascii=False)
        )
        try:
            response = client.messages.create(
                model=PRIMARY_MODEL,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                thinking={"type": "adaptive"},
                output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
                messages=[{"role": "user", "content": prompt}],
            )
            text = next(b.text for b in response.content if b.type == "text")
            parsed = json.loads(text)
            _merge(batch, parsed.get("codes", []))
            usage = response.usage
            cin, cout = PRICING[PRIMARY_MODEL]
            db.log_usage(user_id, project_id, "analysis.open_coding", PRIMARY_MODEL,
                         usage.input_tokens, usage.output_tokens,
                         usage.input_tokens / 1000.0 * cin
                         + usage.output_tokens / 1000.0 * cout)
        except Exception as exc:
            db.log_usage(user_id, project_id, "analysis.open_coding", PRIMARY_MODEL,
                         0, 0, 0.0, success=False, error_message=str(exc)[:300])
            # Local coding for this batch stands; carry on with the rest.
            continue
    return codes


def _merge(batch, returned):
    for item in returned:
        try:
            code = batch[int(item["index"])]
        except (KeyError, ValueError, IndexError):
            continue
        label = (item.get("label") or "").strip()
        if label:
            code["label"] = label[:160]
        literal = (item.get("literal_meaning") or "").strip()
        if literal:
            code["literal_meaning"] = literal[:400]
        if item.get("emotion") in VALID_EMOTIONS:
            code["emotion"] = item["emotion"]
        if item.get("intent") in VALID_INTENTS:
            code["intent"] = item["intent"]
        try:
            conf = float(item.get("confidence"))
            if 0.0 <= conf <= 1.0:
                code["confidence"] = round(conf, 3)
        except (TypeError, ValueError):
            pass
        alts = [str(a).strip() for a in item.get("alternative_interpretations") or []
                if str(a).strip()]
        if alts:
            code["alternative_interpretations"] = alts[:3]
