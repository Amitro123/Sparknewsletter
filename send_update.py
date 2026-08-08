import os
import re
from datetime import datetime
from typing import Iterator
from zoneinfo import ZoneInfo

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DOC_ID = os.getenv("DOC_ID")

ISRAEL_TIMEZONE = ZoneInfo("Asia/Jerusalem")
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

DAILY_HEADING_RE = re.compile(
    r"(?m)^#?\s*עדכון יומי[\s:-]+(?P<date>\d{4}-\d{2}-\d{2})"
)


def require_config() -> None:
    """Validate required environment variables."""
    missing = [
        name
        for name, value in {
            "TELEGRAM_BOT_TOKEN": BOT_TOKEN,
            "TELEGRAM_CHAT_ID": CHAT_ID,
            "DOC_ID": DOC_ID,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(
            "Missing required environment variables: " + ", ".join(missing)
        )


def fetch_google_doc_text(doc_id: str) -> str:
    """Fetch a publicly accessible Google Doc as plain UTF-8 text."""
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    text = response.content.decode("utf-8").strip()
    if not text:
        raise ValueError("Google Doc is empty.")

    return text


def extract_latest_daily_update(text: str) -> tuple[str, str]:
    """
    Extract the final section that starts with:
    # עדכון יומי: YYYY-MM-DD
    """
    matches = list(DAILY_HEADING_RE.finditer(text))

    if not matches:
        raise ValueError(
            "No daily update heading found. Expected: "
            "'# עדכון יומי: YYYY-MM-DD'\n"
            f"Fetched text snippet: {text[:200]!r}"
        )

    latest_match = matches[-1]
    update_date = latest_match.group("date")
    update_text = text[latest_match.start():].strip()

    if not update_text:
        raise ValueError("Latest daily update is empty.")

    return update_date, update_text


def validate_update_is_today(update_date: str) -> None:
    """
    Refuse to publish stale content.

    Gemini is expected to update the Google Doc first and only then dispatch
    this workflow, so the latest section must be dated today in Israel.
    """
    today = datetime.now(ISRAEL_TIMEZONE).date().isoformat()

    if update_date != today:
        raise ValueError(
            f"Latest Google Doc update is dated {update_date}, "
            f"but today in Asia/Jerusalem is {today}. "
            "Refusing to publish stale content."
        )


def split_telegram_message(
    text: str,
    limit: int = TELEGRAM_MAX_MESSAGE_LENGTH,
) -> Iterator[str]:
    """Split long content into Telegram-safe message chunks."""
    remaining = text.strip()

    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit + 1)

        if split_at <= 0:
            split_at = limit

        chunk = remaining[:split_at].strip()
        if chunk:
            yield chunk

        remaining = remaining[split_at:].strip()

    if remaining:
        yield remaining


def send_to_telegram(text: str) -> list[dict]:
    """Publish text to the configured Telegram chat."""
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be configured."
        )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    results: list[dict] = []

    for chunk in split_telegram_message(text):
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(f"Telegram API returned an error: {result}")

        results.append(result)

    return results


def main() -> None:
    require_config()

    print("Fetching latest content from Google Docs...")
    document_text = fetch_google_doc_text(DOC_ID)

    update_date, latest_update = extract_latest_daily_update(document_text)
    validate_update_is_today(update_date)

    print(
        f"Found daily update for {update_date} "
        f"({len(latest_update)} characters)."
    )

    results = send_to_telegram(latest_update)

    print(
        f"Published successfully to Telegram "
        f"({len(results)} message(s))."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Publishing failed: {exc}")
        raise
