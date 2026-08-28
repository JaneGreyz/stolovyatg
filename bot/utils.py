from __future__ import annotations

import re

PHONE_PATTERN = re.compile(
    r"^\+?[78]?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$"
)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return phone.strip()


def is_valid_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 10


def parse_amount(text: str) -> int | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    cleaned = re.sub(
        r"\s*(₽|руб\.?|р\.?)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = cleaned.replace(" ", "")
    if cleaned.isdigit():
        return int(cleaned)
    return None


TME_POST_RE = re.compile(
    r"(?:https?://)?(?:www\.)?t\.me/c/(?P<internal_id>\d+)/(?P<msg_id2>\d+)"
    r"|(?:https?://)?(?:www\.)?t\.me/(?P<username>[a-zA-Z0-9_]+)/(?P<msg_id>\d+)"
)


def parse_telegram_post_link(url: str) -> tuple[int | str, int] | None:
    match = TME_POST_RE.search(url.strip())
    if not match:
        return None
    if match.group("internal_id"):
        return int(f"-100{match.group('internal_id')}"), int(match.group("msg_id2"))
    username = match.group("username")
    if username:
        return f"@{username}", int(match.group("msg_id"))
    return None


def parse_saved_chat_id(raw: str) -> int | str:
    raw = raw.strip()
    if raw.startswith("@") or not re.fullmatch(r"-?\d+", raw):
        return raw
    return int(raw)
