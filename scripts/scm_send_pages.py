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
