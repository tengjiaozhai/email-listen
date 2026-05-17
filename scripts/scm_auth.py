from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import Page, Response

from slider_solver import solve_slider

ENTRY_URL = (
    "https://supply.zte.com.cn/sscm/UI/Web/Application/kxscm/"
    "kxsup_manager/Portal/index.aspx"
)
JIGSAW_PATH = "/zte-bmt-ucs-portalbff/srv/kaptcha/jigsaw"


@dataclass(frozen=True)
class ScmCredentials:
    username: str
    password: str


class JigsawCapture:
    def __init__(self):
        self.data: dict | None = None
        self._event = asyncio.Event()

    async def on_response(self, resp: Response):
        if JIGSAW_PATH in resp.url:
            self.data = await resp.json()
            self._event.set()

    async def wait(self, timeout_s: float = 15.0) -> dict | None:
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout_s)
            return self.data
        except asyncio.TimeoutError:
            return None

    def reset(self):
        self.data = None
        self._event.clear()


def is_callback_url(url: str) -> bool:
    return "Portal/UcsCallBack.aspx" in url


def is_index_url(url: str) -> bool:
    return "/Index.aspx?TYPE=0" in url


async def _human_drag(page: Page, start_x: float, start_y: float, distance: float):
    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    await page.mouse.move(start_x + distance, start_y, steps=30)
    await page.mouse.up()


async def _check_success(page: Page) -> bool:
    if is_index_url(page.url):
        return True
    if await page.locator(".jigsaw-dialog").count():
        return False
    return is_callback_url(page.url)


async def _trigger_jigsaw_request(page: Page, attempt: int):
    if attempt > 1:
        refresh = page.locator(".jigsaw-dialog .el-icon-refresh-right")
        if await refresh.count():
            await refresh.first.click(force=True)
            return
    await page.locator("#btn-signin").click()


async def enter_system_home(page: Page) -> None:
    await page.locator(".agotoSystem").click()
    await page.wait_for_url("**/Index.aspx?TYPE=0", timeout=15000)
    await page.wait_for_timeout(5000)


async def login_and_enter_system(
    page: Page,
    credentials: ScmCredentials,
    artifacts_dir: Path | None = None,
) -> None:
    await page.goto(ENTRY_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)

    privacy = page.locator("#chb_privacy_policy")
    if await privacy.count() and not await privacy.is_checked():
        await privacy.check()

    await page.locator("#btn_login_cl").click()
    await page.wait_for_selector("#input-loginname", timeout=10000)
    await page.fill("#input-loginname", credentials.username)

    password = page.locator("#input-password")
    await password.click()
    await page.wait_for_timeout(200)
    await password.fill(credentials.password)

    if artifacts_dir is not None:
        await page.screenshot(path=str(artifacts_dir / "uac_before_submit.png"), full_page=True)

    for attempt in range(1, 4):
        capture = JigsawCapture()
        page.on("response", capture.on_response)
        capture.reset()
        await _trigger_jigsaw_request(page, attempt)
        data = await capture.wait(timeout_s=15)
        page.remove_listener("response", capture.on_response)
        if not data:
            continue

        solution = solve_slider(data["bo"]["bigImg"], data["bo"]["smallImg"], y_height=data["bo"]["yHeight"])
        dom = await page.evaluate(
            """() => {
                const panel = document.querySelector('#sliderPanel');
                const block = document.querySelector('#block');
                const slider = document.querySelector('#slider');
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
            }"""
        )
        piece_initial_x = dom["block_left"] - dom["panel_left"]
        solution.drag_distance = solution.target_x - piece_initial_x
        start_x = dom["slider_left"] + dom["slider_w"] / 2
        start_y = dom["slider_top"] + dom["slider_h"] / 2
        await _human_drag(page, start_x, start_y, solution.drag_distance)

        for _ in range(20):
            if await _check_success(page):
                await enter_system_home(page)
                return
            await page.wait_for_timeout(500)

    raise RuntimeError("Failed to pass slider captcha after 3 attempts")
