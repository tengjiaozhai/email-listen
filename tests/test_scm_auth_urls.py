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
