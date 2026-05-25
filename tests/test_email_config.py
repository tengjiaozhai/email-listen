import json
from pathlib import Path

import pytest

from email_config import AppConfig, EmailConfig, ScmConfig, WecomConfig, load_config, ConfigError

_WECOM = {"webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"}


def test_load_config_reads_email_fields(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123",
            "mailbox": "INBOX"
        },
        "wecom": _WECOM,
    }))
    config = load_config(config_file)
    assert config.email.imap_host == "imap.tinno.com"
    assert config.email.imap_port == 993
    assert config.email.username == "user@tinno.com"
    assert config.email.password == "pass123"


def test_load_config_uses_scm_defaults(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123"
        },
        "wecom": _WECOM,
    }))
    config = load_config(config_file)
    assert config.scm.username == "TNProject01"
    assert config.scm.password == "Tinno@2030"


def test_load_config_allows_scm_override(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123"
        },
        "scm": {
            "username": "custom_user",
            "password": "custom_pass"
        },
        "wecom": _WECOM,
    }))
    config = load_config(config_file)
    assert config.scm.username == "custom_user"
    assert config.scm.password == "custom_pass"


def test_load_config_raises_on_missing_email_fields(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com"
        }
    }))
    with pytest.raises(ConfigError, match="username"):
        load_config(config_file)


def test_load_config_raises_on_missing_file():
    with pytest.raises(ConfigError, match="not found"):
        load_config(Path("/nonexistent/config.json"))


def test_load_config_default_mailbox(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123"
        },
        "wecom": _WECOM,
    }))
    config = load_config(config_file)
    assert config.email.mailbox == "INBOX"


def test_load_config_default_trigger_recipients_empty(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123"
        },
        "wecom": _WECOM,
    }))
    config = load_config(config_file)
    assert config.email.trigger_recipients == []


def test_load_config_reads_trigger_recipients(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123",
            "trigger_recipients": ["mingjie.shen@tinno.com", "group@tinno.com"]
        },
        "wecom": _WECOM,
    }))
    config = load_config(config_file)
    assert config.email.trigger_recipients == ["mingjie.shen@tinno.com", "group@tinno.com"]


def test_load_config_trigger_recipients_matches_any_in_to_field(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123",
            "trigger_recipients": ["mingjie.shen@tinno.com"]
        },
        "wecom": _WECOM,
    }))
    config = load_config(config_file)
    # 模拟 To 字段包含多个收件人
    to_field = "mingjie.shen@tinno.com, all@tinno.com"
    matched = any(r in to_field for r in config.email.trigger_recipients)
    assert matched is True

    # 不匹配的收件人
    to_field_other = "other@tinno.com, all@tinno.com"
    matched_other = any(r in to_field_other for r in config.email.trigger_recipients)
    assert matched_other is False


def test_load_config_reads_wecom_webhook(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123",
        },
        "wecom": {"webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc"},
    }))
    config = load_config(config_file)
    assert config.wecom.webhook == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc"


def test_load_config_raises_on_missing_wecom(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123",
        },
    }))
    with pytest.raises(ConfigError, match="wecom.webhook"):
        load_config(config_file)


def test_load_config_raises_on_empty_webhook(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123",
        },
        "wecom": {"webhook": ""},
    }))
    with pytest.raises(ConfigError, match="wecom.webhook"):
        load_config(config_file)
