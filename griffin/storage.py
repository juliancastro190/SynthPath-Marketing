"""JSON-file storage shared by anything that needs to persist state across
restarts — tools (reminders, tasks, drafts) and the Tier 4 memory store.

`data/` lives at the repo root and is git-ignored — it's the user's local
runtime data, not source. This is deliberately plain JSON so it's easy to
open and inspect (or edit) by hand.
"""

import json
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_REPO_ROOT, "data")


def _path(filename):
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)


def load(filename, default):
    path = _path(filename)
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save(filename, data):
    with open(_path(filename), "w") as f:
        json.dump(data, f, indent=2)
