from pathlib import Path

from scripts.run_send_record_downloads import build_run_root


def test_build_run_root_places_timestamp_under_download_root(tmp_path: Path):
    assert build_run_root(tmp_path, "20260517_151500") == tmp_path / "20260517_151500"
