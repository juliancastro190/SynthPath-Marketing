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


def _decline_unattended(tool_name, tool_input, description):
    # The heartbeat runs on its own background thread with nobody at the
    # keyboard to ask, so a confirmation-gated tool call must not block on
    # input() forever — same "safe default: don't do it, leave a notice"
    # rule the runner documents for itself. This means a scheduled task
    # can never complete anything consequential (e.g. youtube_produce)
    # fully unattended, by design; it can still do everything free/
    # non-gated and report back what it got done and what it couldn't.
    return False


def team_task(check_config, now=None):
    """Runs a specialist on a fixed schedule without anyone asking it to —
    e.g. "write this week's video script." Config needs `specialist` (a
    name from griffin/agents/team.py) and `task` (plain-language
    instructions). Always worth a look when it produces something, so this
    reports as "alert" (subject to quiet hours, like any other alert) —
    the whole point of scheduling one is that it makes something new."""
    from griffin.agents.team import SPECIALISTS

    check_name = check_config.get("name", "team_task")
    specialist_name = check_config.get("specialist")
    task = check_config.get("task")
    if not specialist_name or not task:
        return [(f"'{check_name}' is misconfigured — needs both 'specialist' and 'task' set.", "alert")]

    specialist = SPECIALISTS.get(specialist_name)
    if specialist is None:
        available = ", ".join(sorted(SPECIALISTS))
        return [(f"'{check_name}' names unknown specialist '{specialist_name}'. Available: {available}.", "alert")]

    try:
        result = specialist.run_task(task, on_confirm=_decline_unattended)
    except Exception as exc:
        return [(f"[{specialist_name}] scheduled task failed: {exc}", "alert")]

    if len(result) > 400:
        result = result[:400] + "… (full output in data/audit.log)"
    return [(f"[{specialist_name}] finished a scheduled task — {result}", "alert")]


CHECK_FUNCTIONS = {
    "stale_open_items": stale_open_items,
    "team_task": team_task,
}
