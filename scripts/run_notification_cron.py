#!/usr/bin/env python3
"""POST /api/cron/notifications (used by Render cron job)."""
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get(
    "RCD_NOTIFICATIONS_CRON_URL",
    "https://river-city-doubles.onrender.com/api/cron/notifications",
).strip()
SECRET = os.environ.get("RCD_CRON_SECRET", "").strip()


def main() -> int:
    if not SECRET:
        print("RCD_CRON_SECRET is not set", file=sys.stderr)
        return 1
    req = urllib.request.Request(
        URL,
        method="POST",
        headers={"X-RCD-Cron": SECRET, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(body)
            return 0 if 200 <= resp.status < 300 else 1
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
