#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Config:
    # Runtime configuration sourced from environment variables.
    base_url: str
    access_token: str
    force_post: bool
    dry_run: bool


class MastodonClient:
    # Thin client for the two Mastodon endpoints used by this automation.
    def __init__(self, base_url: str, access_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token

    def get_json(self, path: str) -> Any:
        # Perform unauthenticated GET requests against the instance API.
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GET failed for {url}: {exc}") from exc

    def post_status(self, status_text: str) -> Mapping[str, Any]:
        # Post as application/x-www-form-urlencoded to mirror the Shortcut behavior.
        url = f"{self.base_url}/api/v1/statuses"
        payload = urllib.parse.urlencode({"status": status_text}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.load(response)
                if not isinstance(data, Mapping):
                    raise RuntimeError("POST response is not a JSON object")
                return data
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"POST failed with HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"POST failed for {url}: {exc}") from exc


def parse_bool_env(name: str, default: str = "false") -> bool:
    # Accepts "true" (case-insensitive) as truthy; everything else is false.
    return os.getenv(name, default).strip().lower() == "true"


def load_config() -> Config:
    # MASTODON_ACCESS_TOKEN is required and should come from GitHub Secrets.
    access_token = os.getenv("MASTODON_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise RuntimeError("Missing env var: MASTODON_ACCESS_TOKEN")

    return Config(
        base_url=os.getenv("MASTODON_BASE_URL", "https://norden.social").strip(),
        access_token=access_token,
        force_post=parse_bool_env("FORCE_POST"),
        dry_run=parse_bool_env("DRY_RUN"),
    )


def should_post_now() -> bool:
    # GitHub Actions now supports timezone-aware schedules, but keep a Berlin local time guard in code.
    now_berlin = datetime.now(ZoneInfo("Europe/Berlin"))
    return now_berlin.weekday() == 0 and now_berlin.hour == 12


def pick_last_week_activity(activity: Any) -> Mapping[str, Any]:
    if not isinstance(activity, list) or not activity:
        raise RuntimeError("Unexpected activity payload: expected non-empty list")

    # Activity data is newest-first. Entry 1 is typically the last completed week.
    candidate = activity[1] if len(activity) >= 2 else activity[0]
    if not isinstance(candidate, Mapping):
        raise RuntimeError("Unexpected activity payload: list items are not objects")
    return candidate


def pick_random_shortcode(emojis: Any) -> str:
    if not isinstance(emojis, list) or not emojis:
        raise RuntimeError("Unexpected emojis payload: expected non-empty list")

    # Select one random custom emoji for the "emoji of the week" line.
    emoji = random.choice(emojis)
    if not isinstance(emoji, Mapping):
        raise RuntimeError("Unexpected emoji payload: expected object")

    shortcode = emoji.get("shortcode")
    if not isinstance(shortcode, str) or not shortcode:
        raise RuntimeError("Emoji payload missing 'shortcode'")
    return shortcode


def build_status(client: MastodonClient) -> str:
    # Build the final German status text exactly as in the original Shortcut.
    activity = client.get_json("/api/v1/instance/activity")
    week = pick_last_week_activity(activity)

    logins = week.get("logins")
    registrations = week.get("registrations")
    if logins is None or registrations is None:
        raise RuntimeError("Activity payload missing 'logins' or 'registrations'")

    emojis = client.get_json("/api/v1/custom_emojis")
    shortcode = pick_random_shortcode(emojis)

    return (
        f"Letzte Woche waren wir {logins} aktive Accounts und {registrations} "
        f"haben sich neu registriert.\n\n"
        f"Unser Emoji der Woche ist \"{shortcode}\": :{shortcode}:"
    )


def run() -> int:
    # Main orchestration: time guard -> compose text -> optional post.
    config = load_config()

    if not config.force_post and not should_post_now():
        now_berlin = datetime.now(ZoneInfo("Europe/Berlin"))
        now_utc = datetime.now(ZoneInfo("UTC"))
        print(
            "Not Monday 12:00 Europe/Berlin; skipping post. "
            f"Current Berlin time is {now_berlin:%Y-%m-%d %H:%M %Z}, "
            f"current UTC time is {now_utc:%Y-%m-%d %H:%M %Z}."
        )
        return 0

    client = MastodonClient(config.base_url, config.access_token)
    status_text = build_status(client)

    print("Composed status:")
    print(status_text)

    if config.dry_run:
        print("DRY_RUN=true, not posting.")
        return 0

    result = client.post_status(status_text)
    print(f"Posted status id: {result.get('id')}")
    return 0


def main() -> int:
    # Keep traceback noise out of CI logs; return clear, user-facing errors instead.
    try:
        return run()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
