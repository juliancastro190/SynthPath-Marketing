"""Persists when each configured check is next due.

Without this, restarting the heartbeat would either reset every timer
(so nothing feels overdue even if it's been days) or fire everything at
once on boot. Reading fresh from disk on every check — rather than
caching in memory — is also what makes the schedule survive a restart
with no special "load on startup" step.
"""

from datetime import datetime

from griffin import storage

FILENAME = "heartbeat_state.json"


def _load():
    return storage.load(FILENAME, {})


def get_next_due(check_name):
    entry = _load().get(check_name)
    if not entry:
        return None
    return datetime.fromisoformat(entry["next_due_at"])


def set_next_due(check_name, when):
    state = _load()
    state[check_name] = {"next_due_at": when.isoformat()}
    storage.save(FILENAME, state)
