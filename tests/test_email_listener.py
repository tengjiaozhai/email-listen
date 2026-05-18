"""Tests for email_listener.py recipient filtering."""

import json
from pathlib import Path

from email_config import load_config


def test_should_trigger_matches_configured_recipient():
    """配置了 trigger_recipients 时，匹配的收件人应触发。"""
    from email_listener import should_trigger

    config = _make_config(trigger_recipients=["mingjie.shen@tinno.com"])
    to_field = "mingjie.shen@tinno.com"
    assert should_trigger(to_field, config) is True


def test_should_trigger_matches_recipient_in_multi_to():
    """To 字段包含多个收件人时，匹配其中一个即触发。"""
    from email_listener import should_trigger

    config = _make_config(trigger_recipients=["mingjie.shen@tinno.com"])
    to_field = "other@tinno.com, mingjie.shen@tinno.com, group@tinno.com"
    assert should_trigger(to_field, config) is True


def test_should_trigger_rejects_non_matching_recipient():
    """收件人不在配置列表中时，不触发。"""
    from email_listener import should_trigger

    config = _make_config(trigger_recipients=["mingjie.shen@tinno.com"])
    to_field = "other@tinno.com"
    assert should_trigger(to_field, config) is False


def test_should_trigger_empty_recipients_matches_all():
    """trigger_recipients 为空时，所有邮件都触发（向后兼容）。"""
    from email_listener import should_trigger

    config = _make_config(trigger_recipients=[])
    to_field = "anyone@tinno.com"
    assert should_trigger(to_field, config) is True


def test_should_trigger_multiple_configured_recipients():
    """配置多个收件人时，匹配任意一个即触发。"""
    from email_listener import should_trigger

    config = _make_config(trigger_recipients=["user1@tinno.com", "group@tinno.com"])
    assert should_trigger("group@tinno.com", config) is True
    assert should_trigger("user1@tinno.com", config) is True
    assert should_trigger("other@tinno.com", config) is False


def test_should_trigger_group_email():
    """群组邮箱也能匹配。"""
    from email_listener import should_trigger

    config = _make_config(trigger_recipients=["scm-group@tinno.com"])
    to_field = "scm-group@tinno.com, mingjie.shen@tinno.com"
    assert should_trigger(to_field, config) is True


def _make_config(trigger_recipients=None):
    """Helper to create a minimal AppConfig with given trigger_recipients."""
    import tempfile
    cfg = {
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123",
        }
    }
    if trigger_recipients is not None:
        cfg["email"]["trigger_recipients"] = trigger_recipients
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(cfg, f)
        f.flush()
        return load_config(Path(f.name))
