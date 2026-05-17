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
