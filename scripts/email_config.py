from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class EmailConfig:
    imap_host: str
    imap_port: int
    username: str
    password: str
    mailbox: str = "INBOX"


@dataclass(frozen=True)
class ScmConfig:
    username: str
    password: str


@dataclass(frozen=True)
class AppConfig:
    email: EmailConfig
    scm: ScmConfig


_SCM_DEFAULTS = ScmConfig(username="TNProject01", password="Tinno@2030")

_REQUIRED_EMAIL_FIELDS = {"imap_host", "imap_port", "username", "password"}


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {path}: {e}") from e

    email_raw = raw.get("email", {})
    missing = _REQUIRED_EMAIL_FIELDS - set(email_raw.keys())
    if missing:
        raise ConfigError(f"Missing email config fields: {', '.join(sorted(missing))}")

    email = EmailConfig(
        imap_host=email_raw["imap_host"],
        imap_port=int(email_raw["imap_port"]),
        username=email_raw["username"],
        password=email_raw["password"],
        mailbox=email_raw.get("mailbox", "INBOX"),
    )

    scm_raw = raw.get("scm", {})
    scm = ScmConfig(
        username=scm_raw.get("username", _SCM_DEFAULTS.username),
        password=scm_raw.get("password", _SCM_DEFAULTS.password),
    )

    return AppConfig(email=email, scm=scm)
