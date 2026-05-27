from pathlib import Path

import py7zr
import pytest

from scripts.scm_send_models import AttachmentTarget, SendRecordRow
from scripts.scm_send_worker import build_manifest_row, extract_download, should_stop


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
    manifest_row = build_manifest_row(row, files, extracted_files=[])
    assert manifest_row["send_number"] == "5001"
    assert sorted(manifest_row["downloads"].keys()) == [
        "dtg_AttachList__ctl3_Linkbutton1",
        "dtg_AttachList__ctl3_Linkbutton2",
    ]
    assert manifest_row["extracted_files"] == []
    assert manifest_row["notification"] is None


def _make_7z(path: Path, filename: str = "content.txt", content: str = "hello") -> None:
    """在 path 创建一个包含单个文本文件的 7z 压缩包。"""
    import io
    with py7zr.SevenZipFile(path, "w") as archive:
        data = content.encode()
        archive.writestr(data, filename)


def test_extract_download_prefers_download1(tmp_path: Path):
    d1 = tmp_path / "download1__notice.7z"
    d2 = tmp_path / "download2__notice.7z"
    _make_7z(d1, "from_d1.txt")
    _make_7z(d2, "from_d2.txt")

    saved = {
        "dtg_AttachList__ctl3_Linkbutton1": d1,
        "dtg_AttachList__ctl3_Linkbutton2": d2,
    }
    result = extract_download(saved, tmp_path)

    assert len(result) > 0, "应返回解压出的文件列表"
    extracted = list(tmp_path.rglob("from_d1.txt"))
    assert extracted, "download1 应被解压"
    assert not list(tmp_path.rglob("from_d2.txt")), "download2 不应被解压"


def test_extract_download_falls_back_to_download2(tmp_path: Path):
    d2 = tmp_path / "download2__notice.7z"
    _make_7z(d2, "from_d2.txt")

    saved = {
        "dtg_AttachList__ctl3_Linkbutton2": d2,
    }
    result = extract_download(saved, tmp_path)

    assert len(result) > 0, "应返回解压出的文件列表"
    extracted = list(tmp_path.rglob("from_d2.txt"))
    assert extracted, "download2 应在没有 download1 时被解压"


def test_extract_download_does_nothing_when_no_files(tmp_path: Path):
    result = extract_download({}, tmp_path)
    assert result == []


def _make_zip(path: Path, filename: str = "content.txt", content: str = "hello") -> None:
    """在 path 创建一个包含单个文本文件的 zip 压缩包。"""
    import zipfile
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(filename, content)


def test_extract_download_handles_zip(tmp_path: Path):
    d1 = tmp_path / "download1__notice.zip"
    _make_zip(d1, "from_zip.txt")

    saved = {"dtg_AttachList__ctl3_Linkbutton1": d1}
    result = extract_download(saved, tmp_path)

    assert list(tmp_path.rglob("from_zip.txt")), "zip 文件应被解压"
    assert len(result) > 0


def test_extract_download_zip_not_in_returned_files(tmp_path: Path):
    d1 = tmp_path / "download1__notice.zip"
    _make_zip(d1, "from_zip.txt")

    saved = {"dtg_AttachList__ctl3_Linkbutton1": d1}
    result = extract_download(saved, tmp_path)

    assert all(p.suffix != ".zip" for p in result), "返回列表不应包含 .zip 文件本身"
