"""Loads config.yaml — Griffin's project-wide, hand-editable configuration:
which tools require confirmation, the per-turn tool-round safety valve, the
heartbeat's checks/intervals/quiet-hours, and the proactive kill switch.

Thresholds, intervals, and safety knobs live here rather than as literals
scattered through the code, so tuning any of them is a one-line edit with
no code change — and re-reading this file on every heartbeat tick (see
runner.py) is what lets the kill switch take effect without a restart.
"""

import os

import yaml

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_REPO_ROOT, "config.yaml")

DEFAULT_CONFIG = {
    "model": {"max_tool_rounds": 8},
    "tools": {"requires_confirmation": [], "confirmation_timeout_seconds": 30},
    "heartbeat": {
        "poll_interval_seconds": 30,
        "quiet_hours": {"start": "22:00", "end": "08:00"},
        "checks": [],
    },
    "kill_switch": {"proactive_paused": False},
}


def _deep_merge(base, override):
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path=None):
    path = path or CONFIG_PATH
    if not os.path.exists(path):
        return dict(DEFAULT_CONFIG)
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULT_CONFIG, data)
