from scripts.scm_send_models import (
    SendRecordRow,
    choose_next_unprocessed,
    detail_url_to_serial_id,
    matches_title_filter,
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


def test_matches_title_filter_exact_match():
    row = SendRecordRow(send_number="5001", serial_id="11",
                        title="P615F03 Z2581 生产技术通知单20260520",
                        sender="u1", sent_at="2026-05-21")
    assert matches_title_filter(row, "P615F03 Z2581 生产技术通知单20260520") is True


def test_matches_title_filter_no_match():
    row = SendRecordRow(send_number="5002", serial_id="12",
                        title="其他标题", sender="u1", sent_at="2026-05-21")
    assert matches_title_filter(row, "P615F03 Z2581 生产技术通知单20260520") is False


def test_matches_title_filter_none_filter_always_matches():
    row = SendRecordRow(send_number="5003", serial_id="13",
                        title="任意标题", sender="u1", sent_at="2026-05-21")
    assert matches_title_filter(row, None) is True
