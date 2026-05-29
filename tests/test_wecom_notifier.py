"""
企微群机器人通知模块测试。
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from scripts.wecom_notifier import notify, send_file, send_text

WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=TEST_KEY"


def _ok_resp(extra: dict | None = None) -> MagicMock:
    """构造 errcode=0 的成功响应 mock。"""
    data = {"errcode": 0, "errmsg": "ok"}
    if extra:
        data.update(extra)
    m = MagicMock()
    m.json.return_value = data
    return m


def _err_resp(errcode: int = 93000, errmsg: str = "invalid webhook url") -> MagicMock:
    """构造 errcode!=0 的失败响应 mock。"""
    m = MagicMock()
    m.json.return_value = {"errcode": errcode, "errmsg": errmsg}
    return m


class TestSendText(unittest.TestCase):
    @patch("requests.post")
    def test_send_text_payload(self, mock_post):
        mock_post.return_value = _ok_resp()
        send_text(WEBHOOK, "SN-20260525-001")

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["msgtype"], "text")
        self.assertIn("SN-20260525-001", payload["text"]["content"])
        self.assertIn("@all", payload["text"]["mentioned_list"])
        self.assertNotIn("@所有人", payload["text"]["content"])

    @patch("requests.post")
    def test_send_text_raises_on_error(self, mock_post):
        mock_post.return_value = _err_resp(93000, "invalid webhook url")
        with self.assertRaises(RuntimeError) as ctx:
            send_text(WEBHOOK, "SN-001")
        self.assertIn("wecom text send failed", str(ctx.exception))


class TestSendFile(unittest.TestCase):
    def _make_temp_file(self, tmp_path: Path, name: str = "test.xlsx") -> Path:
        p = tmp_path / name
        p.write_bytes(b"fake content")
        return p

    @patch("requests.post")
    def test_send_file_calls_upload_then_send(self, mock_post):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "report.xlsx"
            file_path.write_bytes(b"fake")

            upload_resp = _ok_resp({"media_id": "MEDIA_123", "type": "file"})
            send_resp = _ok_resp()
            mock_post.side_effect = [upload_resp, send_resp]

            send_file(WEBHOOK, file_path)

            self.assertEqual(mock_post.call_count, 2)
            # 第一次调用应为 upload_media
            first_call_url = mock_post.call_args_list[0][0][0]
            self.assertIn("upload_media", first_call_url)
            self.assertIn("type=file", first_call_url)
            # 第二次调用应为发送 file 消息
            second_call_kwargs = mock_post.call_args_list[1][1]
            self.assertEqual(second_call_kwargs["json"]["msgtype"], "file")
            self.assertEqual(second_call_kwargs["json"]["file"]["media_id"], "MEDIA_123")

    @patch("requests.post")
    def test_send_file_raises_on_upload_error(self, mock_post):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "report.xlsx"
            file_path.write_bytes(b"fake")

            mock_post.return_value = _err_resp(40004, "media not exist")

            with self.assertRaises(RuntimeError) as ctx:
                send_file(WEBHOOK, file_path)
            self.assertIn("wecom file upload failed", str(ctx.exception))


class TestNotify(unittest.TestCase):
    @patch("requests.post")
    def test_notify_returns_success_dict(self, mock_post):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            f1 = Path(td) / "file1.xlsx"
            f2 = Path(td) / "file2.xlsx"
            f1.write_bytes(b"a")
            f2.write_bytes(b"b")

            # text OK, upload f1 OK, send f1 OK, upload f2 OK, send f2 OK
            mock_post.side_effect = [
                _ok_resp(),                                      # send_text
                _ok_resp({"media_id": "M1", "type": "file"}),   # upload f1
                _ok_resp(),                                      # send f1
                _ok_resp({"media_id": "M2", "type": "file"}),   # upload f2
                _ok_resp(),                                      # send f2
            ]

            result = notify(WEBHOOK, "SN-001", [f1, f2])

            self.assertTrue(result["text_sent"])
            self.assertEqual(sorted(result["files_sent"]), ["file1.xlsx", "file2.xlsx"])
            self.assertIsNone(result["error"])

    @patch("requests.post")
    def test_notify_returns_error_dict_on_failure(self, mock_post):
        mock_post.return_value = _err_resp(93000, "invalid webhook url")

        result = notify(WEBHOOK, "SN-001", [])

        self.assertFalse(result["text_sent"])
        self.assertEqual(result["files_sent"], [])
        self.assertIsNotNone(result["error"])
        self.assertIn("wecom text send failed", result["error"])


if __name__ == "__main__":
    unittest.main()
