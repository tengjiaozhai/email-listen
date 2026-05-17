from __future__ import annotations

import json
from pathlib import Path

from playwright.async_api import Frame, Page

from scripts.scm_send_models import SendRecordRow, sanitize_download_name
from scripts.scm_send_pages import find_notice_attachments


def should_stop(rows: list[SendRecordRow], processed_send_numbers: set[str]) -> bool:
    return all(row.send_number in processed_send_numbers for row in rows)


def build_manifest_row(row: SendRecordRow, files: dict[str, Path]) -> dict:
    return {
        "send_number": row.send_number,
        "serial_id": row.serial_id,
        "title": row.title,
        "sender": row.sender,
        "sent_at": row.sent_at,
        "downloads": {button_id: str(path) for button_id, path in files.items()},
    }


async def download_notice_buttons(
    page: Page,
    right: Frame,
    row: SendRecordRow,
    download_root: Path,
    keyword: str = "生产技术通知单",
) -> dict[str, Path]:
    output_dir = download_root / row.send_number
    output_dir.mkdir(parents=True, exist_ok=True)

    saved: dict[str, Path] = {}
    for target in await find_notice_attachments(right, keyword):
        async with page.expect_download(timeout=10000) as download_info:
            await right.locator(f"#{target.button_id}").click()
        download = await download_info.value
        safe_name = sanitize_download_name(download.suggested_filename)
        prefix = "download1" if target.button_id.endswith("Linkbutton1") else "download2"
        output_path = output_dir / f"{prefix}__{safe_name}"
        await download.save_as(output_path)
        saved[target.button_id] = output_path
    return saved


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps({"records": rows}, ensure_ascii=False, indent=2))
