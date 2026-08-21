"""A plain, append-only audit trail: what Griffin did, and why — every
tool call (whether it needed confirmation, whether it was approved),
every heartbeat notice, and a running tally of estimated model cost, so a
runaway loop is visible immediately instead of showing up as a surprise
bill later.

Deliberately JSON-lines rather than one big JSON blob: entries only ever
get appended, never rewritten, so this avoids a full read-modify-write of
the whole log on every single tool call as it grows. `data/audit.log` is
plain text — one JSON object per line — so it's easy to open, tail, or
grep by hand.
"""

import json
import os
from datetime import datetime, timezone

from griffin import storage

LOG_FILENAME = "audit.log"
COST_FILENAME = "cost.json"

# Rough per-million-token list prices, used only to keep a running
# estimate visible — not meant to be billing-accurate.
_PRICES_PER_MTOK = {
    "claude-sonnet-5": {"input": 3.0, "output": 15.0},
}
_FALLBACK_PRICE = {"input": 3.0, "output": 15.0}

# Prompt caching (griffin/brain/loop.py's _cached_block) has its own
# rates, as a standard multiple of the base input price: writing a new
# cache entry costs more than a normal input token (1.25x for the
# ephemeral/5-minute TTL used here — Anthropic also offers a pricier 1h
# TTL at 2x, not used in this project), reading a cache hit is far
# cheaper (0.1x). Without these, cost tracking would silently under-count
# once caching kicked in — cache tokens arrive on their own usage fields,
# separate from input_tokens, so ignoring them isn't a wash, it's a gap.
_CACHE_WRITE_MULTIPLIER = 1.25
_CACHE_READ_MULTIPLIER = 0.1

_EMPTY_COST_TOTALS = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "estimated_cost_usd": 0.0,
    "calls": 0,
}


def _append(entry):
    os.makedirs(storage.DATA_DIR, exist_ok=True)
    entry = {"at": datetime.now(timezone.utc).isoformat(), **entry}
    log_path = os.path.join(storage.DATA_DIR, LOG_FILENAME)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_tool_call(name, tool_input, required_confirmation, approved, result_text, is_error):
    _append(
        {
            "type": "tool_call",
            "tool": name,
            "input": tool_input,
            "required_confirmation": required_confirmation,
            "approved": approved,
            "is_error": is_error,
            "result": (result_text or "")[:300],
        }
    )


def log_heartbeat_notice(check_name, message, severity):
    # "check_name" rather than "check" — CHECK is a reserved SQL keyword,
    # and lnav (see the Tier 7 log-viewer format) exposes JSON log fields
    # as a queryable SQL table, so an unquoted "check" column breaks its
    # generated CREATE TABLE.
    _append({"type": "heartbeat_notice", "check_name": check_name, "severity": severity, "message": message})


def log_model_usage(model, input_tokens, output_tokens, cache_creation_input_tokens=0, cache_read_input_tokens=0):
    price = _PRICES_PER_MTOK.get(model, _FALLBACK_PRICE)
    cost = (
        (input_tokens / 1_000_000) * price["input"]
        + (output_tokens / 1_000_000) * price["output"]
        + (cache_creation_input_tokens / 1_000_000) * price["input"] * _CACHE_WRITE_MULTIPLIER
        + (cache_read_input_tokens / 1_000_000) * price["input"] * _CACHE_READ_MULTIPLIER
    )

    totals = storage.load(COST_FILENAME, _EMPTY_COST_TOTALS.copy())
    totals["input_tokens"] += input_tokens
    totals["output_tokens"] += output_tokens
    # .get(..., 0) rather than a plain key lookup: a cost.json written
    # before caching existed won't have these two keys yet.
    totals["cache_creation_input_tokens"] = totals.get("cache_creation_input_tokens", 0) + cache_creation_input_tokens
    totals["cache_read_input_tokens"] = totals.get("cache_read_input_tokens", 0) + cache_read_input_tokens
    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"] + cost, 6)
    totals["calls"] += 1
    storage.save(COST_FILENAME, totals)

    _append(
        {
            "type": "model_usage",
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
            "estimated_cost_usd": round(cost, 6),
            "running_total_usd": totals["estimated_cost_usd"],
        }
    )


def running_cost():
    return storage.load(COST_FILENAME, _EMPTY_COST_TOTALS.copy())
