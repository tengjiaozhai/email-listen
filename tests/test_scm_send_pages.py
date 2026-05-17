import pytest

from scripts.scm_send_pages import SupplyReleaseNavigator


class RecorderLocator:
    def __init__(self, calls, selector):
        self.calls = calls
        self.selector = selector

    @property
    def first(self):
        return self

    async def click(self, **kwargs):
        self.calls.append(("click", self.selector, kwargs))

    async def wait_for(self, **kwargs):
        self.calls.append(("wait_for", self.selector, kwargs))


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
    assert leftup.calls[1][0:2] == ("wait_for", "#eaad9d90429c4a259edb77c91fa66743")
    assert leftup.calls[2][0:2] == ("click", "#eaad9d90429c4a259edb77c91fa66743")
