from __future__ import annotations

from playwright.async_api import Frame, Page

from scripts.scm_send_models import AttachmentTarget, SendRecordRow, detail_url_to_serial_id, row_matches_keyword


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
