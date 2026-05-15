#!/usr/bin/env python3
"""Send the River City Doubles example notification email to one address.

Uses RCD_RESEND_API_KEY or RCD_SMTP_* from the environment (or .env in repo root).

Usage:
  python scripts/send_example_email.py md8294@gmail.com
  python scripts/send_example_email.py md8294@gmail.com --name "Mark Davis"
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_ROOT, ".env"))
except ImportError:
    pass

from app import _email_transport_configured, send_example_notification_email  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("to", help="Recipient email address")
    parser.add_argument("--name", default="there", help="Greeting name (first and last)")
    args = parser.parse_args()
    to = args.to.strip().lower()
    if "@" not in to:
        raise SystemExit("Invalid email address.")
    if not _email_transport_configured():
        raise SystemExit(
            "Email not configured. Set RCD_RESEND_API_KEY or RCD_SMTP_PASS + RCD_EMAIL_FROM in .env "
            "(same as Render), or call the hosted API after deploy:\n"
            '  curl -X POST -H "X-RCD-Cron: $RCD_CRON_SECRET" '
            'https://river-city-doubles.onrender.com/api/notifications/example-email '
            '-H "Content-Type: application/json" '
            '-d \'{"to":"' + to + '","name":"' + args.name + '"}\''
        )
    ok, err = send_example_notification_email(to, args.name)
    if ok:
        print(f"Sent example email to {to}")
    else:
        raise SystemExit(f"Send failed: {err}")


if __name__ == "__main__":
    main()
