from __future__ import annotations

import logging
import re
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import httpx

logger = logging.getLogger(__name__)

SHEET_ID_KEY = "daily_menu_sheet_id"
SHEET_GID_KEY = "daily_menu_gid"

SHEET_URL_RE = re.compile(
    r"docs\.google\.com/spreadsheets/d/(?P<sheet_id>[a-zA-Z0-9-_]+)"
)


def parse_sheet_url(url: str) -> tuple[str, int | None]:
    match = SHEET_URL_RE.search(url)
    if not match:
        raise ValueError("Не удалось распознать ссылку на Google Sheets")
    sheet_id = match.group("sheet_id")
    parsed = urlparse(url)
    gid_raw = parse_qs(parsed.query).get("gid", [None])[0]
    if gid_raw is None and parsed.fragment:
        fragment = parse_qs(parsed.fragment.lstrip("#"))
        gid_raw = fragment.get("gid", [None])[0]
    gid = int(gid_raw) if gid_raw else None
    return sheet_id, gid


def build_pdf_export_url(sheet_id: str, gid: int) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=pdf&gid={gid}&portrait=false&fitw=true"
        f"&gridlines=false&printtitle=false&sheetnames=false"
    )


async def save_sheet_menu(db, sheet_id: str, gid: int) -> None:
    await db.set_setting(SHEET_ID_KEY, sheet_id)
    await db.set_setting(SHEET_GID_KEY, str(gid))
    logger.info("Daily menu sheet saved: id=%s gid=%s", sheet_id, gid)


async def get_saved_sheet_menu(db) -> tuple[str, int] | None:
    sheet_id = await db.get_setting(SHEET_ID_KEY)
    gid = await db.get_setting(SHEET_GID_KEY)
    if sheet_id and gid:
        return sheet_id, int(gid)
    return None


async def download_menu_images(sheet_id: str, gid: int) -> list[bytes]:
    url = build_pdf_export_url(sheet_id, gid)
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        pdf_bytes = response.content

    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[bytes] = []
    matrix = fitz.Matrix(2, 2)
    for page_index in range(doc.page_count):
        pixmap = doc[page_index].get_pixmap(matrix=matrix)
        images.append(pixmap.tobytes("png"))
    return images
