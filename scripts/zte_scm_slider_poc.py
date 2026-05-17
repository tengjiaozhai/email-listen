"""
ZTE SCM 滑块验证 PoC — Playwright + OpenCV 自动化登录流程

Usage:
    python3 zte_scm_slider_poc.py --username TNProject01 --password TNProject01
    # or via env vars: ZTE_USERNAME, ZTE_PASSWORD
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from scm_auth import ScmCredentials, login_and_enter_system

ARTIFACTS_ROOT = Path(__file__).parent.parent / "artifacts" / "slider-poc"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("zte-poc")


def _artifact_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = ARTIFACTS_ROOT / ts
    d.mkdir(parents=True, exist_ok=True)
    return d


async def run(username: str, password: str, headless: bool = False):
    artifacts = _artifact_dir()
    log.info("Artifacts → %s", artifacts)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = await context.new_page()

        credentials = ScmCredentials(username=username, password=password)
        await login_and_enter_system(page, credentials, artifacts_dir=artifacts)

        await page.screenshot(path=str(artifacts / "final_state.png"), full_page=True)
        log.info("Login succeeded, final URL: %s", page.url)

        await browser.close()


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ZTE SCM Slider PoC")
    parser.add_argument("--username", default=os.environ.get("ZTE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("ZTE_PASSWORD", ""))
    parser.add_argument("--headless", action="store_true", help="Run headless")
    args = parser.parse_args()

    if not args.username or not args.password:
        log.error("Provide --username/--password or set ZTE_USERNAME/ZTE_PASSWORD")
        sys.exit(1)

    asyncio.run(run(args.username, args.password, headless=args.headless))


if __name__ == "__main__":
    main()
