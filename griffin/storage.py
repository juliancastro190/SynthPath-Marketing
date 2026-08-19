"""JSON-file storage shared by anything that needs to persist state across
restarts — tools (reminders, tasks, drafts) and the Tier 4 memory store.

`data/` lives at the repo root and is git-ignored — it's the user's local
runtime data, not source. This is deliberately plain JSON so it's easy to
open and inspect (or edit) by hand.
"""

import json
import os
import tempfile
import threading

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_REPO_ROOT, "data")

# The heartbeat (Tier 8) can run several checks concurrently, each in its
# own thread, and more than one can share the same file (every check's
# next-due time lives together in heartbeat_state.json) — an
# unsynchronized read-modify-write from two threads at once was observed
# to corrupt the file (interleaved writes producing invalid JSON). This
# lock serializes all load/save calls within the process; save() also
# writes atomically (temp file + rename) so a hard crash mid-write can't
# leave a half-written file behind either.
_lock = threading.Lock()


def _path(filename):
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)


def load(filename, default):
    with _lock:
        path = _path(filename)
        if not os.path.exists(path):
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)


def save(filename, data):
    with _lock:
        path = _path(filename)
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix=f".{filename}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
