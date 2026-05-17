import json
from pathlib import Path

import pytest

from email_config import AppConfig, EmailConfig, ScmConfig, load_config, ConfigError


def test_load_config_reads_email_fields(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "email": {
            "imap_host": "imap.tinno.com",
            "imap_port": 993,
            "username": "user@tinno.com",
            "password": "pass123",
            "mailbox": "INBOX"
        }
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
        }
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
        }
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
        }
    }))
    config = load_config(config_file)
    assert config.email.mailbox == "INBOX"
