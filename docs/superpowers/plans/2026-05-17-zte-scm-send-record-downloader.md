# ZTE SCM Send Record Downloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing slider-login PoC into an end-to-end worker that enters SCC, opens `供方管理 -> 供方发放`, filters `未签收` records, downloads both `下载1` and `下载2` for every `生产技术通知单`, returns to the list, and stops only after all unprocessed records in the current run have been downloaded successfully.

**Architecture:** Keep the existing OpenCV slider solver and Playwright login flow, but extract them into a reusable auth module that lands on `Index.aspx?TYPE=0`. Build a second layer of frame-aware page objects for the legacy ASP.NET frameset (`news`, `leftup`, `right`), then add a worker loop that records processed send numbers locally so the run does not get stuck on still-unsigned rows.

**Tech Stack:** Python 3.11, Playwright async API, existing `scripts/slider_solver.py`, pytest, stdlib `dataclasses`, `pathlib`, `json`

---

## File Structure

- Create: `scripts/scm_auth.py`
  Reusable login helpers: portal entry, slider captcha, callback page, `进入系统`.

- Create: `scripts/scm_send_models.py`
  Dataclasses and pure helper functions for record IDs, attachment selection, processed-set logic, and filename sanitization.

- Create: `scripts/scm_send_pages.py`
  Frame-aware page objects for `供方管理 -> 供方发放`, the guide page, the unsigned-record list page, and the detail/download page.

- Create: `scripts/scm_send_worker.py`
  Orchestrates the list loop, deduplicates already-processed rows in one run, saves downloads, and writes run manifests.

- Create: `scripts/run_send_record_downloads.py`
  CLI entrypoint for the full end-to-end workflow.

- Modify: `scripts/zte_scm_slider_poc.py`
  Reuse `scm_auth.py` instead of keeping a second copy of the login flow.

- Create: `tests/test_scm_auth_urls.py`
  Unit tests for URL and portal-stage helpers.

- Create: `tests/test_scm_send_models.py`
  Unit tests for parsed send IDs, keyword matching, processed-set selection, and filename sanitization.

- Create: `tests/test_scm_send_pages.py`
  Unit tests with recorder fakes for selector order and page-object call flow.

- Create: `tests/test_scm_send_worker.py`
  Unit tests for stop conditions, manifest rows, and duplicate-skip behavior.

- Create: `tests/test_run_send_record_downloads.py`
  Unit tests for CLI helper functions that build run output directories.

- Modify: `docs/research.md`
  Append the live selectors, frame names, URLs, and the observed `选择否` discrepancy.

- Modify: `CHANGELOG.md`
  Record the new downloader capability.

## Observed Live Contracts

- Login still starts at `https://supply.zte.com.cn/sscm/UI/Web/Application/kxscm/kxsup_manager/Portal/index.aspx`.
- `进入系统` is not a plain link. The DOM is `<a href="javascript:;" onclick="linkToHome()" class="agotoSystem">进入系统</a>`.
- Clicking `进入系统` posts `Popup/PopupHandler.ashx?oper=OpenPage` and lands on `https://supply.zte.com.cn/sscm/UI/Web/Application/kxscm/Index.aspx?TYPE=0`.
- `Index.aspx?TYPE=0` is a frameset. Relevant frames are:
  - `news`: top business menu, includes `供方管理`
  - `leftup`: left navigation tree
  - `right`: main business content
- In frame `leftup`, `供方发放` is a collapsed section by default.
  - Section header: `#RightNavigationMenu_MenuSection4_SectionHeader`
  - Hidden panel: `#RightNavigationMenu_MenuSection4_SectionPanel`
  - Clickable entry: `#eaad9d90429c4a259edb77c91fa66743`
- Clicking the menu entry first loads a guide page in frame `right`:
  - URL contains `kxsup_manager/sup_send/sendmanage/SendRecordListNew.aspx?MenuID=eaad9d90429c4a259edb77c91fa66743`
  - Enter button: `#ibtnEnter`
  - Page text says that if a browser-native prompt appears, choose `否`, not `是`
- After clicking `#ibtnEnter`, the actual list page URL is:
  - `https://supply.zte.com.cn/SupplierUI/SendManage/SendRecordList.aspx?...`
- List-page controls:
  - Sign-status select: `#ddlSignStatus`
  - Title filter: `#txtSendTitle`
  - Start date: `#dtbStartDate`
  - End date: `#dtbEndDate`
  - Query button: `#btnQuery`
  - First record link example: `#dtg_Doclist__ctl3_HyperLink1`
- Detail page URL pattern:
  - `https://supply.zte.com.cn/SupplierUI/SendManage/SendRecordDetail.aspx?SendSerialId=<id>`
- Download buttons on the observed detail page:
  - `#dtg_AttachList__ctl3_Linkbutton1`
  - `#dtg_AttachList__ctl3_Linkbutton2`
  - `#btnReturn`
- Both `下载1` and `下载2` triggered a Playwright `download` event and returned the same `.7z` filename in the observed run.
- The current list page also exposes `签收确认` via `#dtg_Doclist__ctl3_Button1`, but the requested workflow did not ask to sign. Do not click it unless the spec changes.

## Design Decisions

- Treat the user’s `点击是` description as environment-specific browser guidance, not a page-DOM action.
  The observed Chromium path has no DOM `是/否` button; the page warns that if a browser-native prompt appears, the correct choice is `否`.

- Do not build the mainline around Computer Use.
  Use Playwright for the real workflow. Keep Computer Use only as a manual fallback during headed exploratory runs if a native browser modal appears outside the DOM.

- Do not rely on `未签收` rows disappearing after download.
  Because the requested workflow does not include `签收确认`, the worker must maintain an in-memory `processed_send_numbers` set for one run and stop when the current query returns no unprocessed rows.

- Search for the target file by keyword, not by table section.
  The observed `生产技术通知单` appeared under `附件`, while `文档` was empty. The worker should scan both sections and match rows whose display name contains `生产技术通知单`.

### Task 1: Extract Reusable Auth And Portal Entry

**Files:**
- Create: `scripts/scm_auth.py`
- Modify: `scripts/zte_scm_slider_poc.py`
- Test: `tests/test_scm_auth_urls.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.scm_auth import is_callback_url, is_index_url


def test_is_callback_url_matches_portal_callback():
    assert is_callback_url(
        "https://supply.zte.com.cn/sscm/UI/Web/Application/kxscm/"
        "kxsup_manager/Portal/UcsCallBack.aspx?code=abc&state=1"
    )
    assert not is_callback_url("https://supply.zte.com.cn/sscm/UI/Web/Application/kxscm/Index.aspx?TYPE=0")


def test_is_index_url_matches_system_home():
    assert is_index_url("https://supply.zte.com.cn/sscm/UI/Web/Application/kxscm/Index.aspx?TYPE=0")
    assert not is_index_url(
        "https://supply.zte.com.cn/SupplierUI/SendManage/SendRecordList.aspx?supplyno=1"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_auth_urls.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.scm_auth'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/scm_auth.py
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
```

Also update `scripts/zte_scm_slider_poc.py` so it imports `ScmCredentials` and `login_and_enter_system()` from `scripts/scm_auth.py` instead of keeping a second copy of the portal flow.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_auth_urls.py -q`

Expected: PASS with `2 passed`

- [ ] **Step 5: Run syntax verification**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m py_compile scripts/scm_auth.py scripts/zte_scm_slider_poc.py`

Expected: no output

- [ ] **Step 6: Commit**

```bash
git add tests/test_scm_auth_urls.py scripts/scm_auth.py scripts/zte_scm_slider_poc.py
git commit -m "feat: extract reusable scm auth flow"
```

### Task 2: Add Supply-Release Navigation Page Objects

**Files:**
- Create: `scripts/scm_send_pages.py`
- Test: `tests/test_scm_send_pages.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from scripts.scm_send_pages import SupplyReleaseNavigator


class RecorderLocator:
    def __init__(self, calls, selector):
        self.calls = calls
        self.selector = selector

    def first(self):
        return self

    async def click(self, **kwargs):
        self.calls.append(("click", self.selector, kwargs))


class RecorderFrame:
    def __init__(self):
        self.calls = []

    def locator(self, selector):
        return RecorderLocator(self.calls, selector)


@pytest.mark.asyncio
async def test_open_supply_release_uses_observed_selectors():
    news = RecorderFrame()
    leftup = RecorderFrame()

    navigator = SupplyReleaseNavigator(news, leftup)
    await navigator.open_supply_release_menu()

    assert news.calls[0][0:2] == ("click", "text=供方管理")
    assert leftup.calls[0][0:2] == ("click", "#RightNavigationMenu_MenuSection4_SectionHeader")
    assert leftup.calls[1][0:2] == ("click", "#eaad9d90429c4a259edb77c91fa66743")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_send_pages.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.scm_send_pages'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/scm_send_pages.py
from __future__ import annotations

from playwright.async_api import Frame, Page


class SupplyReleaseNavigator:
    TOP_MENU = "text=供方管理"
    RELEASE_SECTION = "#RightNavigationMenu_MenuSection4_SectionHeader"
    RELEASE_ENTRY = "#eaad9d90429c4a259edb77c91fa66743"
    GUIDE_ENTER = "#ibtnEnter"

    def __init__(self, news: Frame, leftup: Frame):
        self.news = news
        self.leftup = leftup

    async def open_supply_release_menu(self) -> None:
        await self.news.locator(self.TOP_MENU).first.click()
        await self.leftup.locator(self.RELEASE_SECTION).click()
        await self.leftup.locator(self.RELEASE_ENTRY).click(force=True)


def require_frame(page: Page, name: str) -> Frame:
    for frame in page.frames:
        if frame.name == name:
            return frame
    raise RuntimeError(f"frame not found: {name}")


async def open_supply_release_right_frame(page: Page) -> Frame:
    navigator = SupplyReleaseNavigator(require_frame(page, "news"), require_frame(page, "leftup"))
    await navigator.open_supply_release_menu()
    await page.wait_for_timeout(1500)
    right = require_frame(page, "right")
    if "SendRecordListNew.aspx" in right.url:
        await right.locator(SupplyReleaseNavigator.GUIDE_ENTER).click()
        await page.wait_for_timeout(4000)
        right = require_frame(page, "right")
    return right
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_send_pages.py -q`

Expected: PASS with `1 passed`

- [ ] **Step 5: Run a live smoke check for frame navigation**

Run:

```bash
cd /Users/shenmingjie/tinno/email-listen && \
/opt/anaconda3/envs/py311/bin/python3 - <<'PY'
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from scripts.scm_auth import ScmCredentials, login_and_enter_system
from scripts.scm_send_pages import open_supply_release_right_frame

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 1000}, locale="zh-CN")
        await login_and_enter_system(page, ScmCredentials("TNProject01", "Tinno@2030"), Path("artifacts"))
        right = await open_supply_release_right_frame(page)
        print(right.url)
        await browser.close()

asyncio.run(main())
PY
```

Expected: URL contains `SupplierUI/SendManage/SendRecordList.aspx`

- [ ] **Step 6: Commit**

```bash
git add tests/test_scm_send_pages.py scripts/scm_send_pages.py
git commit -m "feat: add supply release navigator"
```

### Task 3: Model Records, Filter The List, And Open Detail Pages

**Files:**
- Create: `scripts/scm_send_models.py`
- Modify: `scripts/scm_send_pages.py`
- Test: `tests/test_scm_send_models.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.scm_send_models import (
    SendRecordRow,
    choose_next_unprocessed,
    detail_url_to_serial_id,
    row_matches_keyword,
)


def test_detail_url_to_serial_id_extracts_send_record_id():
    assert detail_url_to_serial_id("SendRecordDetail.aspx?SendSerialId=11363656") == "11363656"


def test_choose_next_unprocessed_skips_already_seen_rows():
    rows = [
        SendRecordRow(send_number="5001", serial_id="11", title="A", sender="u1", sent_at="2026-05-15"),
        SendRecordRow(send_number="5002", serial_id="12", title="B", sender="u2", sent_at="2026-05-16"),
    ]
    assert choose_next_unprocessed(rows, {"5001"}).send_number == "5002"


def test_row_matches_keyword_finds_production_notice():
    assert row_matches_keyword("生产技术通知单20260515.7z", "生产技术通知单")
    assert not row_matches_keyword("测试照片.zip", "生产技术通知单")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_send_models.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.scm_send_models'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/scm_send_models.py
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
    return filename.replace("/", "_").replace("\\\\", "_").strip()
```

Also extend `scripts/scm_send_pages.py` with list/detail helpers:

```python
from scripts.scm_send_models import AttachmentTarget, SendRecordRow, detail_url_to_serial_id, row_matches_keyword


async def query_unsigned_records(right: Frame) -> None:
    await right.locator("#ddlSignStatus").select_option("0")
    await right.locator("#btnQuery").click()


async def read_send_rows(right: Frame) -> list[SendRecordRow]:
    rows = []
    links = right.locator("a[href*='SendRecordDetail.aspx']")
    count = await links.count()
    for idx in range(count):
        link = links.nth(idx)
        href = await link.get_attribute("href")
        send_number = (await link.inner_text()).strip()
        serial_id = detail_url_to_serial_id(href)
        row_root = link.locator("xpath=ancestor::tr[1]")
        cells = await row_root.locator("td").all_inner_texts()
        rows.append(
            SendRecordRow(
                send_number=send_number,
                serial_id=serial_id,
                title=cells[1].strip() if len(cells) > 1 else "",
                sender=cells[4].strip() if len(cells) > 4 else "",
                sent_at=cells[5].strip() if len(cells) > 5 else "",
            )
        )
    return rows


async def open_send_record(right: Frame, row: SendRecordRow) -> None:
    await right.locator(f"a[href*='SendRecordDetail.aspx?SendSerialId={row.serial_id}']").first.click()


async def find_notice_attachments(right: Frame, keyword: str) -> list[AttachmentTarget]:
    targets = []
    for button_id in ("dtg_AttachList__ctl3_Linkbutton1", "dtg_AttachList__ctl3_Linkbutton2"):
        locator = right.locator(f"#{button_id}")
        if await locator.count():
            row_text = await locator.locator("xpath=ancestor::tr[1]").inner_text()
            if row_matches_keyword(row_text, keyword):
                targets.append(AttachmentTarget(display_name=row_text, button_id=button_id))
    return targets
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_send_models.py tests/test_scm_send_pages.py -q`

Expected: PASS with `4 passed`

- [ ] **Step 5: Run a live smoke check for one record**

Run:

```bash
cd /Users/shenmingjie/tinno/email-listen && \
/opt/anaconda3/envs/py311/bin/python3 - <<'PY'
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from scripts.scm_auth import ScmCredentials, login_and_enter_system
from scripts.scm_send_models import choose_next_unprocessed
from scripts.scm_send_pages import open_supply_release_right_frame, query_unsigned_records, read_send_rows

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 1000}, locale="zh-CN")
        await login_and_enter_system(page, ScmCredentials("TNProject01", "Tinno@2030"), Path("artifacts"))
        right = await open_supply_release_right_frame(page)
        await query_unsigned_records(right)
        rows = await read_send_rows(right)
        print(len(rows), rows[0].send_number if rows else "EMPTY")
        await browser.close()

asyncio.run(main())
PY
```

Expected: first line prints at least `1 500005314623` for the current observed account state

- [ ] **Step 6: Commit**

```bash
git add tests/test_scm_send_models.py scripts/scm_send_models.py scripts/scm_send_pages.py
git commit -m "feat: add send record models and list helpers"
```

### Task 4: Implement Download Worker And Stop Conditions

**Files:**
- Create: `scripts/scm_send_worker.py`
- Test: `tests/test_scm_send_worker.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from scripts.scm_send_models import AttachmentTarget, SendRecordRow
from scripts.scm_send_worker import build_manifest_row, should_stop


def test_should_stop_when_every_row_has_already_been_processed():
    rows = [
        SendRecordRow(send_number="5001", serial_id="11", title="A", sender="u1", sent_at="2026-05-15"),
        SendRecordRow(send_number="5002", serial_id="12", title="B", sender="u2", sent_at="2026-05-16"),
    ]
    assert should_stop(rows, {"5001", "5002"}) is True
    assert should_stop(rows, {"5001"}) is False


def test_build_manifest_row_writes_button_results():
    row = SendRecordRow(send_number="5001", serial_id="11", title="A", sender="u1", sent_at="2026-05-15")
    files = {
        "dtg_AttachList__ctl3_Linkbutton1": Path("artifacts/5001/download1__notice.7z"),
        "dtg_AttachList__ctl3_Linkbutton2": Path("artifacts/5001/download2__notice.7z"),
    }
    manifest_row = build_manifest_row(row, files)
    assert manifest_row["send_number"] == "5001"
    assert sorted(manifest_row["downloads"].keys()) == [
        "dtg_AttachList__ctl3_Linkbutton1",
        "dtg_AttachList__ctl3_Linkbutton2",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_send_worker.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.scm_send_worker'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/scm_send_worker.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_send_worker.py -q`

Expected: PASS with `2 passed`

- [ ] **Step 5: Run syntax verification**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m py_compile scripts/scm_send_worker.py`

Expected: no output

- [ ] **Step 6: Commit**

```bash
git add tests/test_scm_send_worker.py scripts/scm_send_worker.py
git commit -m "feat: add send record download worker"
```

### Task 5: Add The CLI Loop, Update Docs, And Verify End-To-End

**Files:**
- Create: `scripts/run_send_record_downloads.py`
- Create: `tests/test_run_send_record_downloads.py`
- Modify: `docs/research.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from scripts.run_send_record_downloads import build_run_root


def test_build_run_root_places_timestamp_under_download_root(tmp_path: Path):
    assert build_run_root(tmp_path, "20260517_151500") == tmp_path / "20260517_151500"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_run_send_record_downloads.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.run_send_record_downloads'`

- [ ] **Step 3: Write the CLI and loop implementation**

```python
# scripts/run_send_record_downloads.py
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from scripts.scm_auth import ScmCredentials, login_and_enter_system
from scripts.scm_send_models import choose_next_unprocessed
from scripts.scm_send_pages import (
    open_send_record,
    open_supply_release_right_frame,
    query_unsigned_records,
    read_send_rows,
    require_frame,
)
from scripts.scm_send_worker import build_manifest_row, download_notice_buttons, should_stop, write_manifest


def build_run_root(download_root: Path, timestamp: str) -> Path:
    return download_root / timestamp


async def run(username: str, password: str, download_root: Path, headless: bool, limit: int | None) -> None:
    processed: set[str] = set()
    manifest_rows: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
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
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download production notices from SCM send records")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--download-root", type=Path, default=Path("artifacts/send-record-downloads"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    asyncio.run(run(args.username, args.password, args.download_root, args.headless, args.limit))


if __name__ == "__main__":
    main()
```

Append to `docs/research.md`:

```markdown
## 2026-05-17 供方发放自动化补充

- 系统入口页点击 `进入系统` 后进入 `Index.aspx?TYPE=0`
- 顶部业务菜单 frame 名称：`news`
- 左侧功能树 frame 名称：`leftup`
- 主内容 frame 名称：`right`
- `供方发放` 菜单需要先展开 `#RightNavigationMenu_MenuSection4_SectionHeader`
- 引导页按钮：`#ibtnEnter`
- 列表页控件：`#ddlSignStatus`、`#btnQuery`、`#dtg_Doclist__ctl3_HyperLink1`
- 详情页下载按钮：`#dtg_AttachList__ctl3_Linkbutton1`、`#dtg_AttachList__ctl3_Linkbutton2`
- 页面文案提示若浏览器原生弹窗出现，应选择 `否`
```

Append to `CHANGELOG.md`:

```markdown
## 2026-05-17

- Added a design and implementation path for end-to-end SCM send-record downloads after slider login
```

- [ ] **Step 4: Run the full verification**

Run:

```bash
cd /Users/shenmingjie/tinno/email-listen && \
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_scm_auth_urls.py \
  tests/test_scm_send_models.py \
  tests/test_scm_send_pages.py \
  tests/test_scm_send_worker.py \
  tests/test_run_send_record_downloads.py -q
```

Expected: PASS with all new tests green

Run:

```bash
cd /Users/shenmingjie/tinno/email-listen && \
/opt/anaconda3/envs/py311/bin/python3 scripts/run_send_record_downloads.py \
  --username TNProject01 \
  --password 'Tinno@2030' \
  --headless \
  --limit 1 \
  --download-root artifacts/send-record-downloads/e2e
```

Expected:
- login succeeds through the slider flow
- system enters `Index.aspx?TYPE=0`
- `供方发放` guide page opens and `#ibtnEnter` is clicked
- list page remains filtered to `未签收`
- a detail page opens for an unprocessed row
- both `下载1` and `下载2` produce files on disk
- `run.json` is written under the timestamped run directory

- [ ] **Step 5: Commit**

```bash
git add tests/test_run_send_record_downloads.py scripts/run_send_record_downloads.py docs/research.md CHANGELOG.md
git commit -m "feat: add scm send record downloader cli"
```

## Self-Review

- Spec coverage:
  - `点击登录 -> 输入账号密码 -> 通过滑块验证码 -> 点击进入系统`: Task 1
  - `供方管理 -> 供方发放 -> 进入供方发放页面`: Task 2
  - `筛选/获取未签收发放单`: Task 3
  - `点击发放单编号`: Task 3
  - `下载生产技术通知单右侧的下载1/下载2`: Task 4
  - `返回列表，继续下一个发放单`: Task 5
  - `全部下载成功后结束任务`: Task 4 and Task 5 via processed-set stop condition

- Placeholder scan:
  - No `TODO`/`TBD`
  - All tasks include concrete files, code, commands, and expected outcomes

- Type consistency:
  - `SendRecordRow.send_number` is the run-level dedupe key across Tasks 3-5
  - `detail_url_to_serial_id()` always feeds `SendRecordRow.serial_id`
  - download button IDs are reused consistently as manifest keys
