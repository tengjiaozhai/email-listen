# scripts/run_send_record_downloads.py
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

import requests

log = logging.getLogger(__name__)

# Allow running as `python3 scripts/run_send_record_downloads.py` from project root
if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright

from scm_auth import ScmCredentials, login_and_enter_system
from scm_send_models import choose_next_unprocessed, matches_title_filter
from scm_send_pages import (
    open_send_record,
    open_supply_release_right_frame,
    query_unsigned_records,
    read_send_rows,
    require_frame,
)
from scm_send_worker import build_manifest_row, download_notice_buttons, should_stop, write_manifest
from wecom_notifier import notify


def build_run_root(download_root: Path, timestamp: str) -> Path:
    return download_root / timestamp


async def run(username: str, password: str, download_root: Path, headless: bool, limit: int | None, webhook: str, title_filter: str | None = None) -> None:
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

            try:
                await login_and_enter_system(page, ScmCredentials(username, password), run_root)
            except Exception as login_err:
                log.error("SCM 登录失败: %s", login_err)
                if webhook:
                    try:
                        resp = requests.post(webhook, json={
                            "msgtype": "text",
                            "text": {
                                "content": (
                                    f"【SCM 登录失败告警】\n"
                                    f"自动化流程已中止。\n"
                                    f"错误：{login_err}\n"
                                    f"截图：{run_root / 'slider_failed.png'}\n"
                                    "请人工登录处理。"
                                ),
                                "mentioned_list": ["@all"],
                            },
                        }, timeout=10)
                        if resp.json().get("errcode", 0) != 0:
                            log.warning("Login alert webhook returned error: %s", resp.json())
                    except Exception as alert_err:
                        log.warning("Failed to send login alert: %s", alert_err)
                raise
            right = await open_supply_release_right_frame(page)
            await query_unsigned_records(right)

            while True:
                rows = await read_send_rows(right)
                if not rows or should_stop(rows, processed):
                    break

                eligible = [r for r in rows if matches_title_filter(r, title_filter)]
                if not eligible:
                    log.warning("SCM 列表中无标题匹配 %r 的未签收记录，跳过本次下载", title_filter)
                    break

                row = choose_next_unprocessed(eligible, processed)
                if row is None:
                    break

                await open_send_record(right, row)
                await page.wait_for_timeout(3000)
                right = require_frame(page, "right")
                files, extracted = await download_notice_buttons(page, right, row, run_root)
                notification = notify(webhook, row.send_number, extracted)
                manifest_rows.append(build_manifest_row(row, files, extracted, notification))
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
    parser.add_argument("--download-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--webhook", required=True)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be a positive integer")
    asyncio.run(run(args.username, args.password, args.download_root, args.headless, args.limit, args.webhook))


if __name__ == "__main__":
    main()
