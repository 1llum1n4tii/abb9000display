
#!/usr/bin/env python3
"""
Poll ntfy topics and run configured commands when new messages arrive.

Usage:
    python3 display-notifications.py
    python3 display-notifications.py --config display-notifications.json

Commands are configured as argument arrays. To run shell syntax, explicitly
use ["/bin/bash", "-lc", "your command here"].
"""

import argparse
import heapq
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_CONFIG = Path(__file__).with_name("display-notifications.json")
STOP = threading.Event()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("display-notifications")


def handle_signal(signum, _frame):
    log.info("Received signal %s; shutting down.", signum)
    STOP.set()


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_atomic(path, data):
    """Write state atomically to avoid corrupting it on interruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=path.name + ".",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def ntfy_url(base_url, topic, cursor=None):
    params = {"poll": "1"}
    if cursor:
        params["since"] = cursor
    else:
        params["since"] = "latest"

    return (
        f"{base_url.rstrip('/')}/{topic}/json?"
        f"{urlencode(params)}"
    )


def fetch_messages(base_url, topic, cursor, timeout):
    """Return JSON events from one bounded ntfy poll."""
    request = Request(
        ntfy_url(base_url, topic, cursor),
        headers={"User-Agent": "abb9000display-notifications/1.0"},
    )

    with urlopen(request, timeout=timeout) as response:
        events = []
        for line in response:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                log.warning("Ignoring invalid JSON from topic %s", topic)
                continue
            if isinstance(event, dict):
                events.append(event)
        return events


def message_environment(event):
    """Expose notification fields to commands as environment variables."""
    env = os.environ.copy()
    env.update({
        "NTFY_ID": str(event.get("id", "")),
        "NTFY_TIME": str(event.get("time", "")),
        "NTFY_TOPIC": str(event.get("topic", "")),
        "NTFY_MESSAGE": str(event.get("message", "")),
        "NTFY_TITLE": str(event.get("title", "")),
        "NTFY_PRIORITY": str(event.get("priority", "")),
        "NTFY_TAGS": ",".join(map(str, event.get("tags", []))),
        "NTFY_RAW": json.dumps(event, separators=(",", ":")),
    })
    return env


def launch_command(command, event, description):
    """Start a configured command without blocking notification polling."""
    if not isinstance(command, list) or not command:
        log.error("Invalid command for %s; expected a non-empty array", description)
        return

    if not all(isinstance(arg, str) for arg in command):
        log.error("Invalid command arguments for %s", description)
        return

    try:
        process = subprocess.Popen(
            command,
            env=message_environment(event),
            stdin=subprocess.DEVNULL,
            # Inherit stdout/stderr so a service manager can capture logs.
            start_new_session=True,
        )
        log.info(
            "Started %s (pid=%s, topic=%s, notification=%s)",
            description,
            process.pid,
            event.get("topic", ""),
            event.get("id", ""),
        )
    except OSError:
        log.exception("Could not start %s", description)


class NotificationWorker:
    def __init__(self, config, config_path):
        self.config = config
        self.config_path = config_path.resolve()
        self.base_url = config.get("base_url", "https://ntfy.sh").rstrip("/")
        self.interval = float(config.get("poll_interval_seconds", 5))
        self.timeout = float(config.get("request_timeout_seconds", 10))
        self.state_path = Path(
            config.get(
                "state_file",
                str(self.config_path.with_name("display-notifications-state.json")),
            )
        )
        if not self.state_path.is_absolute():
            self.state_path = self.config_path.parent / self.state_path

        if self.interval <= 0 or self.timeout <= 0:
            raise ValueError("Polling interval and request timeout must be positive")

        self.topics = config.get("topics", [])
        if not isinstance(self.topics, list):
            raise ValueError("'topics' must be a list")

        self.state = {}
        if self.state_path.exists():
            self.state = load_json(self.state_path)

        # Heap entries are (due_monotonic_time, sequence, command, event, label).
        self.delayed = []
        self.sequence = 0
        self.reset_keys = {}

    def persist_state(self):
        save_json_atomic(self.state_path, self.state)

    def schedule_delayed(self, topic_config, event):
        policy = topic_config.get("delayed_policy", "reset")

        for index, action in enumerate(topic_config.get("delayed_actions", [])):
            delay = float(action.get("delay_seconds", 0))
            command = action.get("command")

            if delay < 0:
                log.error("Negative delay configured for topic %s", event.get("topic"))
                continue

            key = (event.get("topic"), index)
            if policy == "reset":
                # A newer notification replaces this action's pending timer.
                self.reset_keys[key] = self.reset_keys.get(key, 0) + 1
                generation = self.reset_keys[key]
            elif policy == "parallel":
                generation = None
            else:
                log.error("Unknown delayed_policy %r; use reset or parallel", policy)
                continue

            self.sequence += 1
            heapq.heappush(
                self.delayed,
                (
                    time.monotonic() + delay,
                    self.sequence,
                    key,
                    generation,
                    command,
                    dict(event),
                    f"delayed action {index + 1} for {event.get('topic')}",
                ),
            )
            log.info(
                "Scheduled delayed action for topic %s in %.1f seconds",
                event.get("topic"),
                delay,
            )

    def run_due_actions(self):
        now = time.monotonic()
        while self.delayed and self.delayed[0][0] <= now:
            _, _, key, generation, command, event, label = heapq.heappop(
                self.delayed
            )
            if generation is not None and self.reset_keys.get(key) != generation:
                continue
            launch_command(command, event, label)

    def handle_message(self, topic_config, event):
        log.info(
            "New notification: topic=%s title=%r message=%r id=%s",
            event.get("topic"),
            event.get("title", ""),
            event.get("message", ""),
            event.get("id", ""),
        )

        for index, command in enumerate(topic_config.get("on_message", [])):
            launch_command(command, event, f"immediate action {index + 1}")

        self.schedule_delayed(topic_config, event)

    def poll_topic(self, topic_config):
        topic = topic_config["topic"]
        cursor = self.state.get(topic)

        try:
            events = fetch_messages(
                self.base_url, topic, cursor, self.timeout
            )
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            log.warning("Polling topic %s failed: %s", topic, exc)
            return
        except Exception:
            log.exception("Unexpected error polling topic %s", topic)
            return

        # First run: establish a baseline and do not trigger cached messages.
        if cursor is None:
            message_events = [
                e for e in events
                if e.get("event") == "message" and e.get("id")
            ]
            if message_events:
                self.state[topic] = message_events[-1]["id"]
                self.persist_state()
            log.info("Initialized baseline for topic %s", topic)
            return

        changed = False
        for event in events:
            if event.get("event") != "message" or not event.get("id"):
                continue

            # ntfy returns messages in chronological order.
            self.handle_message(topic_config, event)
            self.state[topic] = event["id"]
            changed = True

        if changed:
            self.persist_state()

    def run(self):
        log.info(
            "Starting notification worker: %d topic(s), poll interval %.1fs",
            len(self.topics),
            self.interval,
        )

        for topic_config in self.topics:
            topic = topic_config.get("topic")
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError("Every topic requires a non-empty 'topic'")

        while not STOP.is_set():
            started = time.monotonic()

            for topic_config in self.topics:
                if STOP.is_set():
                    break
                self.poll_topic(topic_config)

            self.run_due_actions()

            elapsed = time.monotonic() - started
            STOP.wait(max(0, self.interval - elapsed))

        log.info("Notification worker stopped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"JSON config file (default: {DEFAULT_CONFIG})",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        config = load_json(args.config)
        NotificationWorker(config, args.config).run()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        log.error("Cannot start worker: %s", exc)
        return 1
    except KeyboardInterrupt:
        STOP.set()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

