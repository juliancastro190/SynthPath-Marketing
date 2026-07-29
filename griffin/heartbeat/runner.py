"""The heartbeat: a background loop, separate from the conversation loop,
that wakes on an interval, runs whatever checks are due, and files
anything noteworthy into the notice inbox.

Runs as its own standalone process (heartbeat_main.py) so it keeps beating
independent of whether a text or voice session happens to be open — and so
moving it to an always-on host later is just running this same script
there, not a rewrite.

None of the built-in checks perform a consequential action, so none of
them need to pause for the user's approval. If a future check ever does,
it must not block this loop indefinitely waiting for a person who isn't
there — it should time out into a safe default (do nothing, leave a
notice) rather than hang, the same way Tier 6's confirmation gate will
have to behave for anything triggered from here.
"""

import threading
from datetime import datetime, time, timedelta, timezone

from griffin.heartbeat import notices
from griffin.heartbeat.checks import CHECK_FUNCTIONS
from griffin.heartbeat.config import load_config
from griffin.heartbeat.state import get_next_due, set_next_due


def _parse_hhmm(value):
    hour, minute = (int(x) for x in value.split(":"))
    return time(hour=hour, minute=minute)


def _in_quiet_hours(quiet_hours, now):
    start = _parse_hhmm(quiet_hours["start"])
    end = _parse_hhmm(quiet_hours["end"])
    current = now.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end  # window wraps past midnight


class HeartbeatRunner:
    def __init__(self, config=None):
        self.config = config or load_config()
        self._stop = threading.Event()
        self._running_lock = threading.Lock()
        self._running_checks = set()

    def run_forever(self):
        poll_interval = self.config.get("poll_interval_seconds", 30)
        print(f"Heartbeat running. Polling every {poll_interval}s. Ctrl+C to stop.")
        try:
            while not self._stop.is_set():
                self.tick()
                self._stop.wait(poll_interval)
        except KeyboardInterrupt:
            pass

    def tick(self, now=None):
        """Run whatever configured checks are currently due. Safe to call
        directly (e.g. from tests) without starting the background loop."""
        now = now or datetime.now(timezone.utc)
        for check_config in self.config.get("checks", []):
            if not check_config.get("enabled", True):
                continue
            name = check_config["name"]
            due = get_next_due(name)
            if due is not None and now < due:
                continue
            with self._running_lock:
                if name in self._running_checks:
                    continue  # still running from an earlier tick — don't stack
                self._running_checks.add(name)
            threading.Thread(target=self._run_check, args=(check_config, now), daemon=True).start()

    def _run_check(self, check_config, now):
        name = check_config["name"]
        try:
            check_fn = CHECK_FUNCTIONS.get(check_config.get("type", name))
            if check_fn is None:
                print(f"[heartbeat] unknown check type for '{name}', skipping")
                return
            results = check_fn(check_config, now=now)
            in_quiet = _in_quiet_hours(self.config.get("quiet_hours", {}), now)
            for message, severity in results:
                notices.add_notice(name, message, severity)
                if severity == "alert" and not in_quiet:
                    print(f"\n[Griffin] {message}")
        finally:
            interval = timedelta(seconds=check_config.get("interval_seconds", 300))
            set_next_due(name, now + interval)
            with self._running_lock:
                self._running_checks.discard(name)

    def stop(self):
        self._stop.set()
