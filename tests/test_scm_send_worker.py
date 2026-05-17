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
