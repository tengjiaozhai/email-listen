from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class SendRecordRow:
    send_number: str
    serial_id: str
    title: str
    sender: str
    sent_at: str


@dataclass(frozen=True)
class AttachmentTarget:
    display_name: str
    button_id: str


def detail_url_to_serial_id(href: str) -> str:
    parsed = urlparse(href)
    return parse_qs(parsed.query)["SendSerialId"][0]


def row_matches_keyword(display_name: str, keyword: str) -> bool:
    return keyword in display_name


def choose_next_unprocessed(rows: list[SendRecordRow], processed_send_numbers: set[str]) -> SendRecordRow | None:
    for row in rows:
        if row.send_number not in processed_send_numbers:
            return row
    return None


def record_download_dir(root: Path, send_number: str) -> Path:
    return root / send_number


def sanitize_download_name(filename: str) -> str:
    return filename.replace("/", "_").replace("\\", "_").strip()


def matches_title_filter(row: SendRecordRow, title_filter: "str | None") -> bool:
    """title_filter 为 None 时匹配所有行；否则要求 row.title 与 title_filter 精确相等。"""
    if title_filter is None:
        return True
    return row.title == title_filter
