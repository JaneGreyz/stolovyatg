from __future__ import annotations

from html import escape

from bot.texts import (
    ADMIN_MONTH_LOW_RATINGS,
    ADMIN_MONTH_NO_LOW_RATINGS,
    ADMIN_MONTH_NO_REVIEWS,
    ADMIN_MONTH_STATS_HEADER,
    ADMIN_MONTH_STATS_RATING,
    ADMIN_MONTH_STATS_SUM,
    ADMIN_MONTH_STATS_TOTAL,
    STATUS_LABELS,
)


def _month_title(year_month: str) -> str:
    year, month = year_month.split("-")
    months = (
        "январь", "февраль", "март", "апрель", "май", "июнь",
        "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
    )
    return f"{months[int(month) - 1].capitalize()} {year}"


def _format_review_line(row: dict) -> str:
    stars = "⭐" * row["rating"]
    comment = (row["comment"] or "").strip()
    comment_line = f'\n   💬 {escape(comment)}' if comment else ""
    return (
        f"• #{row['order_id']} | {stars} ({row['rating']}/5) | "
        f"{escape(row['guest_name'])} | {escape(row['address_short'])}"
        f"{comment_line}"
    )


def build_month_stats_messages(stats: dict) -> list[str]:
    period = _month_title(stats["year_month"])
    lines = [
        ADMIN_MONTH_STATS_HEADER.format(period=period),
        ADMIN_MONTH_STATS_TOTAL.format(total=stats["total_orders"]),
    ]

    if stats["count_with_amount"]:
        lines.append(
            ADMIN_MONTH_STATS_SUM.format(
                total_sum=stats["total_sum"],
                count=stats["count_with_amount"],
            )
        )
    else:
        lines.append("💰 Сумма заказов: нет данных (менеджеры не указали суммы).")

    if stats["by_status"]:
        lines.append("\n<b>По статусам:</b>")
        for status, count in stats["by_status"].items():
            label = STATUS_LABELS.get(status, status)
            lines.append(f"  • {label}: {count}")

    if stats["avg_rating"] is not None:
        lines.append(
            ADMIN_MONTH_STATS_RATING.format(
                avg=stats["avg_rating"],
                count=len(stats["reviews"]),
            )
        )
    else:
        lines.append("\n⭐ Отзывов за месяц пока нет.")

    messages = ["\n".join(lines)]

    low = stats["low_ratings"]
    if low:
        low_lines = [ADMIN_MONTH_LOW_RATINGS]
        for row in low:
            low_lines.append(_format_review_line(row))
        messages.extend(_split_message("\n".join(low_lines)))
    elif stats["reviews"]:
        messages.append(ADMIN_MONTH_NO_LOW_RATINGS)
    else:
        messages.append(ADMIN_MONTH_NO_REVIEWS)

    return messages


def _split_message(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        chunk = f"{current}\n{line}".strip() if current else line
        if len(chunk) > limit:
            if current:
                parts.append(current)
            current = line
        else:
            current = chunk
    if current:
        parts.append(current)
    return parts
