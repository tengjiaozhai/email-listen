# scripts/scm_send_worker.py
from __future__ import annotations

import json
import logging
from pathlib import Path

import py7zr
from playwright.async_api import Frame, Page

from scm_send_models import SendRecordRow, sanitize_download_name
from scm_send_pages import find_notice_attachments

log = logging.getLogger(__name__)


def should_stop(rows: list[SendRecordRow], processed_send_numbers: set[str]) -> bool:
    return all(row.send_number in processed_send_numbers for row in rows)


def build_manifest_row(
    row: SendRecordRow,
    files: dict[str, Path],
    extracted_files: list[Path],
    notification: dict | None = None,
) -> dict:
    return {
        "send_number": row.send_number,
        "serial_id": row.serial_id,
        "title": row.title,
        "sender": row.sender,
        "sent_at": row.sent_at,
        "downloads": {button_id: str(path) for button_id, path in files.items()},
        "extracted_files": [str(p) for p in extracted_files],
        "notification": notification,
    }


def extract_download(saved: dict[str, Path], output_dir: Path) -> list[Path]:
    """解压 saved 中优先级最高的 7z 文件到 output_dir。

    优先解压 download1（Linkbutton1），没有时才解压 download2（Linkbutton2）。
    返回解压出的普通文件路径列表（不含目录和 .7z 文件）。
    """
    if not saved:
        return []

    d1_key = next((k for k in saved if k.endswith("Linkbutton1")), None)
    d2_key = next((k for k in saved if k.endswith("Linkbutton2")), None)
    target = saved.get(d1_key) if d1_key else saved.get(d2_key) if d2_key else None

    if target is None:
        return []

    log.info("解压 %s -> %s", target.name, output_dir)
    with py7zr.SevenZipFile(target, mode="r") as archive:
        archive.extractall(path=output_dir)

    return [p for p in output_dir.glob("*") if p.is_file() and p.suffix != ".7z"]


async def download_notice_buttons(
    page: Page,
    right: Frame,
    row: SendRecordRow,
    download_root: Path,
    keyword: str = "生产技术通知单",
) -> tuple[dict[str, Path], list[Path]]:
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

    extracted = extract_download(saved, output_dir)
    return saved, extracted


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps({"records": rows}, ensure_ascii=False, indent=2))
