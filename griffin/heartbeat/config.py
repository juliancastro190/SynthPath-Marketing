"""Loads heartbeat.yaml — the knobs for what gets checked and how often.

Intervals, thresholds, and quiet hours are exactly the things you'll want
to tune constantly, so they live in one editable file instead of being
scattered through the code as literals.
"""

import os

import yaml

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(_REPO_ROOT, "heartbeat.yaml")

DEFAULT_CONFIG = {
    "poll_interval_seconds": 30,
    "quiet_hours": {"start": "22:00", "end": "08:00"},
    "checks": [],
}


def load_config(path=None):
    path = path or CONFIG_PATH
    if not os.path.exists(path):
        return dict(DEFAULT_CONFIG)
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return {**DEFAULT_CONFIG, **data}
