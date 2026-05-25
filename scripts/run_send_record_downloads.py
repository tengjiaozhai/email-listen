# scripts/run_send_record_downloads.py
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Allow running as `python3 scripts/run_send_record_downloads.py` from project root
if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright

from scm_auth import ScmCredentials, login_and_enter_system
from scm_send_models import choose_next_unprocessed
from scm_send_pages import (
    open_send_record,
    open_supply_release_right_frame,
    query_unsigned_records,
    read_send_rows,
    require_frame,
)
from scm_send_worker import build_manifest_row, download_notice_buttons, should_stop, write_manifest


def build_run_root(download_root: Path, timestamp: str) -> Path:
    return download_root / timestamp


async def run(username: str, password: str, download_root: Path, headless: bool, limit: int | None) -> None:
    processed: set[str] = set()
    manifest_rows: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        try:
            context = await browser.new_context(viewport={"width": 1600, "height": 1000}, locale="zh-CN", accept_downloads=True)
            page = await context.new_page()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_root = build_run_root(download_root, timestamp)
            run_root.mkdir(parents=True, exist_ok=True)

            await login_and_enter_system(page, ScmCredentials(username, password), run_root)
            right = await open_supply_release_right_frame(page)
            await query_unsigned_records(right)

            while True:
                rows = await read_send_rows(right)
                if not rows or should_stop(rows, processed):
                    break

                row = choose_next_unprocessed(rows, processed)
                if row is None:
                    break

                await open_send_record(right, row)
                await page.wait_for_timeout(3000)
                right = require_frame(page, "right")
                files = await download_notice_buttons(page, right, row, run_root)
                manifest_rows.append(build_manifest_row(row, files))
                processed.add(row.send_number)

                await right.locator("#btnReturn").click()
                await page.wait_for_timeout(2000)
                right = require_frame(page, "right")
                await query_unsigned_records(right)

                if limit is not None and len(processed) >= limit:
                    break

            write_manifest(run_root / "run.json", manifest_rows)
        finally:
            await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download production notices from SCM send records")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--download-root", type=Path, default=Path("."))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    asyncio.run(run(args.username, args.password, args.download_root, args.headless, args.limit))


if __name__ == "__main__":
    main()
