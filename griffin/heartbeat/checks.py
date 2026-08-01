"""Built-in heartbeat checks.

Each takes its own config dict (a `checks:` entry from heartbeat.yaml) and
the current time, and returns a list of (message, severity) pairs — empty
most of the time, since checks are quiet by default and only worth
surfacing when something's actually notable.

Adding a new check means writing one function here and registering it in
CHECK_FUNCTIONS, plus an entry in heartbeat.yaml — never touching the
runner.
"""

from datetime import datetime, timedelta, timezone

from griffin import storage
from griffin.etsy.client import EtsyClient, EtsyError


def _open_stale_items(filename, stale_after, now):
    items = storage.load(filename, [])
    stale = []
    for item in items:
        if item.get("done"):
            continue
        created_at = datetime.fromisoformat(item["created_at"])
        if now - created_at >= stale_after:
            stale.append(item)
    return stale


def stale_open_items(check_config, now=None):
    """Reminders/tasks that have sat open longer than `stale_after_minutes`.
    More than `alert_threshold` of them is worth an interruption; any
    nonzero count still goes into the calm log."""
    now = now or datetime.now(timezone.utc)
    stale_after = timedelta(minutes=check_config.get("stale_after_minutes", 1440))
    alert_threshold = check_config.get("alert_threshold", 3)

    stale_reminders = _open_stale_items("reminders.json", stale_after, now)
    stale_tasks = _open_stale_items("tasks.json", stale_after, now)
    total = len(stale_reminders) + len(stale_tasks)
    if total == 0:
        return []

    parts = []
    if stale_reminders:
        parts.append(f"{len(stale_reminders)} reminder(s)")
    if stale_tasks:
        parts.append(f"{len(stale_tasks)} task(s)")
    message = f"You have {' and '.join(parts)} that have been open a while — want a recap?"
    severity = "alert" if total > alert_threshold else "info"
    return [(message, severity)]


def etsy_unshipped_orders(check_config, now=None):
    """Paid Etsy orders that have sat unshipped longer than
    `stale_after_hours`. Silently does nothing if no shop is connected yet
    (EtsyError) rather than raising — same "quiet unless there's something
    to say" posture as every other check, just with an extra failure mode
    (not connected) that isn't the user's problem to see a traceback for."""
    now = now or datetime.now(timezone.utc)
    stale_after = timedelta(hours=check_config.get("stale_after_hours", 48))
    alert_threshold = check_config.get("alert_threshold", 1)

    try:
        receipts = EtsyClient().list_receipts(was_shipped=False)
    except EtsyError:
        return []

    stale = []
    for r in receipts:
        created = r.get("created_timestamp")
        if created is None:
            continue
        created_at = datetime.fromtimestamp(created, tz=timezone.utc)
        if now - created_at >= stale_after:
            stale.append(r)
    if not stale:
        return []

    message = f"You have {len(stale)} Etsy order(s) unshipped for over {check_config.get('stale_after_hours', 48)}h — want a recap?"
    severity = "alert" if len(stale) >= alert_threshold else "info"
    return [(message, severity)]


def etsy_low_inventory(check_config, now=None):
    """Active Etsy listings at or below `low_quantity_threshold`."""
    threshold = check_config.get("low_quantity_threshold", 2)

    try:
        listings = EtsyClient().list_active_listings(limit=100)
    except EtsyError:
        return []

    low = [l for l in listings if l.get("quantity", 0) <= threshold]
    if not low:
        return []

    names = ", ".join(l["title"] for l in low[:5])
    message = f"{len(low)} Etsy listing(s) are low on stock: {names}{'...' if len(low) > 5 else ''}"
    return [(message, "alert")]


CHECK_FUNCTIONS = {
    "stale_open_items": stale_open_items,
    "etsy_unshipped_orders": etsy_unshipped_orders,
    "etsy_low_inventory": etsy_low_inventory,
}
