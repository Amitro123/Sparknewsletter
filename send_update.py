import os
import re
from datetime import datetime
from typing import Iterator
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, NavigableString, Tag
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
REQUEST_TIMEOUT = (10, 30)  # 10s connect timeout, 30s read timeout

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


def clean_google_url(url: str) -> str:
    """Extract actual destination URL from Google's redirect wrapper if present."""
    parsed = urlparse(url)
    if "google.com" in parsed.netloc and parsed.path.endswith("/url"):
        query = parse_qs(parsed.query)
        if "q" in query:
            return query["q"][0]
    return url


def convert_gdoc_node_to_telegram_html(node) -> str:
    """Recursively convert Google Doc HTML DOM nodes into Telegram-compatible HTML."""
    if isinstance(node, NavigableString):
        text = str(node)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()

    if name in ["head", "script", "style"]:
        return ""

    style = node.get("style", "").lower().replace(" ", "")
    is_bold = (
        "font-weight:700" in style
        or "font-weight:bold" in style
        or name in ["b", "strong"]
    )
    is_italic = (
        "font-style:italic" in style
        or name in ["i", "em"]
    )

    children_content = "".join(
        convert_gdoc_node_to_telegram_html(child) for child in node.children
    )
    res = children_content

    if is_bold and res.strip():
        res = f"<b>{res}</b>"
    if is_italic and res.strip():
        res = f"<i>{res}</i>"

    if name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        res = f"\n\n<b>{res}</b>\n"
    elif name == "p":
        res = f"\n{res}"
    elif name == "a":
        href = clean_google_url(node.get("href", ""))
        if href and res.strip():
            href_escaped = href.replace("&", "&amp;").replace('"', "&quot;")
            res = f'<a href="{href_escaped}">{children_content}</a>'
    elif name == "li":
        res = f"\n• {res}"
    elif name in ["ul", "ol"]:
        res = f"{res}\n"

    return res


def convert_markdown_links_to_html(text: str) -> str:
    """Convert leftover markdown links [text](url) to HTML <a href='url'>text</a>."""
    def _repl(match):
        label = match.group(1)
        url = match.group(2)
        url_escaped = url.replace("&", "&amp;").replace('"', "&quot;")
        return f'<a href="{url_escaped}">{label}</a>'

    return re.sub(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', _repl, text)


def fetch_google_doc_html(doc_id: str) -> str:
    """Fetch a publicly accessible Google Doc as formatted HTML and convert to Telegram HTML."""
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"

    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    html_content = response.content.decode("utf-8", errors="replace")
    if not html_content.strip():
        raise ValueError("Google Doc is empty.")

    soup = BeautifulSoup(html_content, "html.parser")
    body = soup.find("body") or soup

    telegram_html = convert_gdoc_node_to_telegram_html(body)
    telegram_html = convert_markdown_links_to_html(telegram_html)

    telegram_html = re.sub(r"\n{3,}", "\n\n", telegram_html).strip()
    return telegram_html


def extract_latest_daily_update(text: str) -> tuple[str, str]:
    """
    Extract the final section that starts with:
    # עדכון יומי: YYYY-MM-DD
    """
    plain_text = re.sub(r"<[^>]+>", "", text)
    matches = list(DAILY_HEADING_RE.finditer(plain_text))

    if not matches:
        raise ValueError(
            "No daily update heading found. Expected: "
            "'# עדכון יומי: YYYY-MM-DD'\n"
            f"Fetched text snippet: {text[:200]!r}"
        )

    latest_match = matches[-1]
    update_date = latest_match.group("date")

    html_matches = list(DAILY_HEADING_RE.finditer(text))
    if html_matches:
        latest_html_match = html_matches[-1]
        update_text = text[latest_html_match.start():].strip()
    else:
        update_text = text[latest_match.start():].strip()

    if not update_text:
        raise ValueError("Latest daily update is empty.")

    return update_date, update_text


def validate_update_is_today(update_date: str) -> None:
    """Refuse to publish stale content."""
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
    """Publish text to the configured Telegram chat with HTML formatting."""
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
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(f"Telegram API returned an error: {result}")

        results.append(result)

    return results


def main() -> None:
    require_config()

    print("Fetching latest content from Google Docs...")
    document_text = fetch_google_doc_html(DOC_ID)

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
