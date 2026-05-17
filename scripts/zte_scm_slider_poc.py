"""
ZTE SCM 滑块验证 PoC — Playwright + OpenCV 自动化登录流程

Usage:
    python3 zte_scm_slider_poc.py --username TNProject01 --password TNProject01
    # or via env vars: ZTE_USERNAME, ZTE_PASSWORD
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import math
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, Response

from slider_solver import SliderSolution, draw_overlay, solve_slider

# ── Config ─────────────────────────────────────────────────────────────────

ENTRY_URL = (
    "https://supply.zte.com.cn/sscm/UI/Web/Application/kxscm/"
    "kxsup_manager/Portal/index.aspx"
)
JIGSAW_PATH = "/zte-bmt-ucs-portalbff/srv/kaptcha/jigsaw"

MAX_RETRIES = 3
ARTIFACTS_ROOT = Path(__file__).parent.parent / "artifacts" / "slider-poc"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("zte-poc")


# ── Artifact helpers ───────────────────────────────────────────────────────

def _artifact_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = ARTIFACTS_ROOT / ts
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Human-like drag ────────────────────────────────────────────────────────

async def _human_drag(page: Page, start_x: float, start_y: float, distance: float):
    """Drag from (start_x, start_y) rightward by `distance` px with easing."""
    steps = random.randint(25, 35)
    duration = random.randint(350, 600)
    step_delay = duration / steps / 1000.0

    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.05, 0.12))

    for i in range(1, steps + 1):
        t = i / steps
        # Ease-out cubic
        eased = 1 - (1 - t) ** 3
        x = start_x + distance * eased
        y = start_y + random.uniform(-1.5, 1.5)
        await page.mouse.move(x, y)
        await asyncio.sleep(step_delay)

    # Overshoot + settle
    overshoot = random.uniform(2, 5)
    await page.mouse.move(start_x + distance + overshoot, start_y)
    await asyncio.sleep(random.uniform(0.03, 0.08))
    await page.mouse.move(start_x + distance, start_y)
    await asyncio.sleep(random.uniform(0.05, 0.1))

    await page.mouse.up()


# ── Jigsaw interceptor ─────────────────────────────────────────────────────

class JigsawCapture:
    """Intercepts the jigsaw API response and stores the payload."""

    def __init__(self):
        self.data: dict | None = None
        self._event = asyncio.Event()

    async def on_response(self, resp: Response):
        if JIGSAW_PATH in resp.url:
            try:
                body = await resp.json()
                self.data = body
                self._event.set()
                log.info("Captured jigsaw response (yHeight=%s)", body.get("bo", {}).get("yHeight"))
            except Exception as e:
                log.warning("Failed to parse jigsaw response: %s", e)

    async def wait(self, timeout_s: float = 10.0) -> dict | None:
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout_s)
            return self.data
        except asyncio.TimeoutError:
            log.warning("Timed out waiting for jigsaw response")
            return None

    def reset(self):
        self.data = None
        self._event.clear()


# ── Main flow ──────────────────────────────────────────────────────────────

async def run(username: str, password: str, headless: bool = False):
    artifacts = _artifact_dir()
    log.info("Artifacts → %s", artifacts)

    run_log: dict = {"username": username, "attempts": []}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = await context.new_page()

        # ── Step 1: Entry page ──────────────────────────────────────────────
        log.info("Opening entry page: %s", ENTRY_URL)
        await page.goto(ENTRY_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # Check privacy checkbox
        checkbox = page.locator("#chb_privacy_policy")
        if await checkbox.count() > 0:
            is_checked = await checkbox.is_checked()
            if not is_checked:
                await checkbox.check()
                log.info("Checked privacy policy")

        # Click login
        login_btn = page.locator("#btn_login_cl")
        await login_btn.click()
        log.info("Clicked login button")

        # ── Step 2: UAC login page ──────────────────────────────────────────
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_selector("#input-loginname", timeout=8000)
        log.info("UAC login page loaded")

        await page.fill("#input-loginname", username)

        # Password: click first to remove readonly, then type
        pwd_field = page.locator("#input-password")
        await pwd_field.click()
        await page.wait_for_timeout(200)
        await pwd_field.fill(password)

        # Save pre-submit screenshot
        await page.screenshot(path=str(artifacts / "uac_before_submit.png"), full_page=True)

        # ── Step 3: Login with jigsaw interception (retry loop) ─────────────
        for attempt in range(1, MAX_RETRIES + 1):
            log.info("=== Attempt %d / %d ===", attempt, MAX_RETRIES)
            attempt_log: dict = {"attempt": attempt}

            capture = JigsawCapture()
            page.on("response", capture.on_response)
            capture.reset()

            # Click sign-in
            await page.click("#btn-signin")
            log.info("Clicked sign-in")

            # Wait for jigsaw response
            jigsaw_data = await capture.wait(timeout_s=15)
            page.remove_listener("response", capture.on_response)

            if jigsaw_data is None:
                log.warning("No jigsaw response received")
                attempt_log["status"] = "no_jigsaw_response"
                run_log["attempts"].append(attempt_log)
                # Retry: close dialog if open, re-click login
                await _dismiss_and_retry_login(page, artifacts, attempt)
                continue

            # Save raw jigsaw JSON
            (artifacts / "jigsaw_raw.json").write_text(json.dumps(jigsaw_data, ensure_ascii=False, indent=2))

            bo = jigsaw_data.get("bo", {})
            big_url = bo.get("bigImg", "")
            small_url = bo.get("smallImg", "")
            y_height = bo.get("yHeight", 60)

            if not big_url or not small_url:
                log.warning("Missing bigImg or smallImg in response")
                attempt_log["status"] = "missing_images"
                run_log["attempts"].append(attempt_log)
                await _dismiss_and_retry_login(page, artifacts, attempt)
                continue

            # Save decoded images
            big_bytes = base64.b64decode(big_url.split(",")[1])
            small_bytes = base64.b64decode(small_url.split(",")[1])
            (artifacts / "big.png").write_bytes(big_bytes)
            (artifacts / "small.png").write_bytes(small_bytes)

            # Solve
            solution = solve_slider(big_url, small_url, y_height=y_height)
            log.info("Solver: target_x=%d confidence=%.3f", solution.target_x, solution.confidence)

            # Read DOM positions for piece_initial_x
            try:
                dom_info = await page.evaluate("""() => {
                    const panel = document.querySelector('#sliderPanel');
                    const block = document.querySelector('#block');
                    const slider = document.querySelector('#slider');
                    if (!panel || !block || !slider) return null;
                    const pr = panel.getBoundingClientRect();
                    const br = block.getBoundingClientRect();
                    const sr = slider.getBoundingClientRect();
                    return {
                        panel_left: pr.left,
                        block_left: br.left,
                        slider_left: sr.left,
                        slider_top: sr.top,
                        slider_w: sr.width,
                        slider_h: sr.height,
                    };
                }""")
            except Exception:
                dom_info = None

            if dom_info:
                piece_initial_x = dom_info["block_left"] - dom_info["panel_left"]
                solution.piece_initial_x = int(piece_initial_x)
                solution.drag_distance = solution.target_x - piece_initial_x
                attempt_log["dom"] = dom_info
                log.info("DOM: piece_initial_x=%.0f drag_distance=%.0f", piece_initial_x, solution.drag_distance)
            else:
                log.warning("Could not read slider DOM; using defaults")

            # Draw overlay
            draw_overlay(big_bytes, small_bytes, solution, str(artifacts / "overlay.png"))

            # Screenshot before drag
            await page.screenshot(path=str(artifacts / "jigsaw_dialog.png"), full_page=True)

            # Update attempt log
            attempt_log.update({
                "status": "solved",
                "target_x": solution.target_x,
                "drag_distance": solution.drag_distance,
                "confidence": solution.confidence,
                "y_height": y_height,
            })

            # ── Step 4: Drag ────────────────────────────────────────────────
            if dom_info and solution.drag_distance > 0:
                sx = dom_info["slider_left"] + dom_info["slider_w"] / 2
                sy = dom_info["slider_top"] + dom_info["slider_h"] / 2
                log.info("Dragging: (%.0f, %.0f) → +%.0f px", sx, sy, solution.drag_distance)
                await _human_drag(page, sx, sy, solution.drag_distance)
                await page.wait_for_timeout(1500)

                # Check success
                success = await _check_success(page)
                attempt_log["drag_result"] = "success" if success else "failed"
                log.info("Drag result: %s", "SUCCESS" if success else "FAILED")

                if success:
                    run_log["attempts"].append(attempt_log)
                    break
            else:
                attempt_log["drag_result"] = "skipped_bad_distance"

            run_log["attempts"].append(attempt_log)

            # Retry
            if attempt < MAX_RETRIES:
                await _dismiss_and_retry_login(page, artifacts, attempt)

        # ── Step 5: Final state ─────────────────────────────────────────────
        await page.screenshot(path=str(artifacts / "final_state.png"), full_page=True)
        run_log["final_url"] = page.url

        # Save run.json
        (artifacts / "run.json").write_text(json.dumps(run_log, ensure_ascii=False, indent=2))
        log.info("Run log saved to %s", artifacts / "run.json")

        await browser.close()

    return run_log


async def _dismiss_and_retry_login(page: Page, artifacts: Path, attempt: int):
    """Try to refresh captcha or re-click login for retry."""
    log.info("Preparing retry (attempt %d)...", attempt)
    try:
        refresh = page.locator(".el-icon-refresh-right")
        if await refresh.count() > 0 and await refresh.is_visible():
            await refresh.click()
            log.info("Clicked refresh icon")
            await page.wait_for_timeout(1000)
            return
    except Exception:
        pass

    # Fallback: close dialog and re-click sign-in
    try:
        close_btn = page.locator(".el-dialog__close, .el-icon-close")
        if await close_btn.count() > 0:
            await close_btn.first.click()
            await page.wait_for_timeout(500)
    except Exception:
        pass

    # Re-click sign-in if still on login page
    signin = page.locator("#btn-signin")
    if await signin.count() > 0:
        await page.wait_for_timeout(500)


async def _check_success(page: Page) -> bool:
    """Check if login succeeded after drag."""
    try:
        # Check if authentication dialog is gone
        auth_dialog = page.locator(".el-dialog:has-text('Authentication'), .el-dialog:has-text('验证')")
        if await auth_dialog.count() > 0 and await auth_dialog.first.is_visible():
            return False

        # Check if we navigated away from login
        url = page.url
        if "login" not in url.lower() and "uac" not in url.lower():
            return True

        # Check for error messages
        error = page.locator(".el-message--error, .error-msg")
        if await error.count() > 0:
            return False

        # Check for success indicators
        success = page.locator(".el-message--success, .main-content, .dashboard")
        if await success.count() > 0:
            return True

        return False
    except Exception:
        return False


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
