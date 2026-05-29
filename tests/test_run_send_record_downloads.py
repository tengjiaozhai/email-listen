from pathlib import Path
import subprocess
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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


# --limit CLI validation tests

def _run_cli(*extra_args):
    return subprocess.run(
        [sys.executable, "scripts/run_send_record_downloads.py",
         "--username", "u", "--password", "p", "--webhook", "http://x",
         *extra_args],
        capture_output=True,
        cwd=str(Path(__file__).parent.parent),
    )


def test_limit_zero_rejected():
    result = _run_cli("--limit", "0")
    assert result.returncode != 0
    assert b"positive integer" in result.stderr


def test_limit_negative_rejected():
    result = _run_cli("--limit", "-1")
    assert result.returncode != 0
    assert b"positive integer" in result.stderr


def test_limit_positive_accepted_by_parser():
    # Verify parser itself accepts --limit 1 (will fail later due to no real browser, that's OK)
    result = _run_cli("--limit", "1")
    # Must NOT fail with "positive integer" error
    assert b"positive integer" not in result.stderr


# Login failure alert tests

def test_login_failure_sends_webhook_alert(tmp_path):
    from scripts.run_send_record_downloads import run

    async def _run():
        with patch("scripts.run_send_record_downloads.async_playwright") as mock_pw, \
             patch("scripts.run_send_record_downloads.requests.post") as mock_post:

            mock_post.return_value = MagicMock(**{"json.return_value": {"errcode": 0}})

            browser = AsyncMock()
            context = AsyncMock()
            page = AsyncMock()
            browser.new_context.return_value = context
            context.new_page.return_value = page

            pw_instance = AsyncMock()
            pw_instance.chromium.launch.return_value = browser
            mock_pw.return_value.__aenter__.return_value = pw_instance

            with patch("scripts.run_send_record_downloads.login_and_enter_system",
                       side_effect=RuntimeError("Failed to pass slider captcha after 3 attempts")):
                try:
                    await run("u", "p", tmp_path, True, None, "http://webhook")
                except RuntimeError:
                    pass

            mock_post.assert_called_once()
            payload = mock_post.call_args[1]["json"]
            assert payload["msgtype"] == "text"
            assert "SCM 登录失败告警" in payload["text"]["content"]
            assert "@all" in payload["text"]["mentioned_list"]

    asyncio.run(_run())


def test_login_failure_no_webhook_does_not_call_post(tmp_path):
    from scripts.run_send_record_downloads import run

    async def _run():
        with patch("scripts.run_send_record_downloads.async_playwright") as mock_pw, \
             patch("scripts.run_send_record_downloads.requests.post") as mock_post:

            browser = AsyncMock()
            context = AsyncMock()
            page = AsyncMock()
            browser.new_context.return_value = context
            context.new_page.return_value = page

            pw_instance = AsyncMock()
            pw_instance.chromium.launch.return_value = browser
            mock_pw.return_value.__aenter__.return_value = pw_instance

            with patch("scripts.run_send_record_downloads.login_and_enter_system",
                       side_effect=RuntimeError("login failed")):
                try:
                    await run("u", "p", tmp_path, True, None, "")
                except RuntimeError:
                    pass

            mock_post.assert_not_called()

    asyncio.run(_run())
