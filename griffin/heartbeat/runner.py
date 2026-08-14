"""The heartbeat: a background loop, separate from the conversation loop,
that wakes on an interval, runs whatever checks are due, and files
anything noteworthy into the notice inbox.

Runs as its own standalone process (heartbeat_main.py) so it keeps beating
independent of whether a text or voice session happens to be open — and so
moving it to an always-on host later is just running this same script
there, not a rewrite.

Config is re-read from disk on every tick rather than cached, which is
what lets the kill switch (kill_switch.proactive_paused in config.yaml)
take effect immediately without restarting this process.

None of the built-in checks perform a consequential action, so none of
them need to pause for the user's approval. If a future check ever does,
it must not block this loop indefinitely waiting for a person who isn't
there — it should time out into a safe default (do nothing, leave a
notice) rather than hang, the same way the confirmation gate in
brain/loop.py behaves for anything triggered from a live conversation.
"""

import threading
from datetime import datetime, time, timedelta, timezone

from griffin import audit
from griffin.heartbeat import discord_push, notices
from griffin.heartbeat.checks import CHECK_FUNCTIONS
from griffin.heartbeat.state import get_next_due, set_next_due
from griffin.project_config import load_config


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
        # None means "reload config.yaml fresh every tick" (production).
        # A fixed dict is mainly useful for tests, which shouldn't depend
        # on whatever's in the real config.yaml on disk.
        self._fixed_config = config
        self._running_lock = threading.Lock()
        self._running_checks = set()
        self._stop = threading.Event()

    @property
    def config(self):
        if self._fixed_config is not None:
            return self._fixed_config
        return load_config()

    def run_forever(self):
        print("Heartbeat running. Ctrl+C to stop.")
        try:
            while not self._stop.is_set():
                config = self.config  # one fresh read per loop iteration
                self.tick(now=None, config=config)
                self._stop.wait(config.get("heartbeat", {}).get("poll_interval_seconds", 30))
        except KeyboardInterrupt:
            pass

    def stop(self):
        self._stop.set()

    def tick(self, now=None, config=None):
        """Run whatever configured checks are currently due. Safe to call
        directly (e.g. from tests) without starting the background loop."""
        now = now or datetime.now(timezone.utc)
        config = config if config is not None else self.config
        heartbeat_config = config.get("heartbeat", {})

        if config.get("kill_switch", {}).get("proactive_paused", False):
            return  # paused: the loop keeps beating, but does nothing

        for check_config in heartbeat_config.get("checks", []):
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
            threading.Thread(
                target=self._run_check,
                args=(check_config, heartbeat_config, now),
                daemon=True,
            ).start()

    def _run_check(self, check_config, heartbeat_config, now):
        name = check_config["name"]
        try:
            check_fn = CHECK_FUNCTIONS.get(check_config.get("type", name))
            if check_fn is None:
                print(f"[heartbeat] unknown check type for '{name}', skipping")
                return
            results = check_fn(check_config, now=now)
            in_quiet = _in_quiet_hours(
                heartbeat_config.get("quiet_hours", {"start": "22:00", "end": "08:00"}), now
            )
            for message, severity in results:
                notices.add_notice(name, message, severity)
                audit.log_heartbeat_notice(name, message, severity)
                if severity == "alert" and not in_quiet:
                    print(f"\n[Griffin] {message}")
                    discord_push.send_dm(message)
        finally:
            interval = timedelta(seconds=check_config.get("interval_seconds", 300))
            set_next_due(name, now + interval)
            with self._running_lock:
                self._running_checks.discard(name)
