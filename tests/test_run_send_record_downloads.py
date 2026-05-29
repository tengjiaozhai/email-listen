from pathlib import Path

from scripts.run_send_record_downloads import build_run_root


def test_build_run_root_places_timestamp_under_download_root(tmp_path: Path):
    assert build_run_root(tmp_path, "20260517_151500") == tmp_path / "20260517_151500"


from scripts.scm_send_models import SendRecordRow, matches_title_filter


def test_title_filter_selects_only_matching_row():
    rows = [
        SendRecordRow(send_number="5001", serial_id="11",
                      title="目标标题 生产技术通知单20260520", sender="u1", sent_at="2026-05-21"),
        SendRecordRow(send_number="5002", serial_id="12",
                      title="另一个标题", sender="u2", sent_at="2026-05-21"),
    ]
    eligible = [r for r in rows if matches_title_filter(r, "目标标题 生产技术通知单20260520")]
    assert [r.send_number for r in eligible] == ["5001"]


def test_title_filter_none_keeps_all_rows():
    rows = [
        SendRecordRow(send_number="5001", serial_id="11",
                      title="任意标题A", sender="u1", sent_at="2026-05-21"),
        SendRecordRow(send_number="5002", serial_id="12",
                      title="任意标题B", sender="u2", sent_at="2026-05-21"),
    ]
    eligible = [r for r in rows if matches_title_filter(r, None)]
    assert len(eligible) == 2
