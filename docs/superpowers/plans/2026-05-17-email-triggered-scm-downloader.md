# 邮件触发 SCM 自动下载 实施计划

> **自动化代理说明：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 来逐任务执行本计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 当 `mingjie.shen@tinno.com` 收到新邮件时，自动触发完整的 SCM 发放单下载流程（登录 → 供方发放 → 下载附件）。

**架构：** 重构 `email_listener.py`，从 JSON 配置文件（`config.json`）读取邮件凭据。添加回调钩子，每封新邮件到达时通过 `run_send_record_downloads.py` 启动 SCM 下载流程。SCM 登录凭据固定在代码中；邮件凭据由用户配置。首次使用时提示用户创建 `config.json`。

**技术栈：** Python 3.11, imapclient, asyncio, JSON 配置, 现有 SCM 模块

---

## 文件结构

- 新建: `config.json.example`
  首次用户使用的配置文件模板。

- 新建: `scripts/email_config.py`
  配置加载器：读取 `config.json`，校验必填字段，提供 SCM 默认值。

- 新建: `tests/test_email_config.py`
  配置加载和校验的单元测试。

- 移动: `email_listener.py` → `scripts/email_listener.py`
  重构为：从 JSON 读取配置，接受新邮件回调，触发 SCM 下载。

- 修改: `.gitignore`
  添加 `config.json` 防止提交凭据。

- 修改: `SKILL.md`
  添加首次使用配置说明。

- 修改: `CHANGELOG.md`
  记录邮件触发下载功能。

## 配置设计

`config.json` 结构：
```json
{
  "email": {
    "imap_host": "imap.tinno.com",
    "imap_port": 993,
    "username": "mingjie.shen@tinno.com",
    "password": "Smj0409!@#",
    "mailbox": "INBOX"
  },
  "scm": {
    "username": "TNProject01",
    "password": "Tinno@2030"
  }
}
```

SCM 凭据有默认值（`TNProject01`/`Tinno@2030`），可选覆盖。邮件凭据无默认值，用户必须提供。

---

### 任务 1：添加配置加载模块

**涉及文件：**
- 新建: `scripts/email_config.py`
- 新建: `tests/test_email_config.py`
- 新建: `config.json.example`

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_email_config.py
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
```

- [ ] **步骤 2：运行测试验证失败**

运行: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_email_config.py -q`

预期: 失败，报错 `ModuleNotFoundError: No module named 'email_config'`

- [ ] **步骤 3：编写最小实现**

```python
# scripts/email_config.py
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
```

同时创建 `config.json.example`：

```json
{
  "email": {
    "imap_host": "imap.tinno.com",
    "imap_port": 993,
    "username": "your_email@tinno.com",
    "password": "your_email_password",
    "mailbox": "INBOX"
  },
  "scm": {
    "username": "TNProject01",
    "password": "Tinno@2030"
  }
}
```

- [ ] **步骤 4：运行测试验证通过**

运行: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_email_config.py -q`

预期: 通过，`6 passed`

- [ ] **步骤 5：提交**

```bash
git add scripts/email_config.py tests/test_email_config.py config.json.example
git commit -m "feat: add email config loader with JSON support"
```

### 任务 2：重构 email_listener.py 并添加回调支持

**涉及文件：**
- 移动: `email_listener.py` → `scripts/email_listener.py`
- 修改: `scripts/email_listener.py`

- [ ] **步骤 1：移动文件**

```bash
git mv email_listener.py scripts/email_listener.py
```

- [ ] **步骤 2：重构为使用配置和回调**

新的 `scripts/email_listener.py` 需要：
1. 从 `email_config` 导入配置
2. 接受回调函数 `on_new_email(subject, sender, date)`
3. 从 `config.json` 加载配置（默认路径），或接受路径参数
4. 新邮件到达时调用回调

```python
# scripts/email_listener.py
"""
邮件实时监听 — IMAP IDLE 协议，邮件到达时服务器主动推送通知。
支持回调钩子，新邮件到达时触发自定义处理。
"""

from __future__ import annotations

import ssl
import time
import logging
import email
from email.header import decode_header
from pathlib import Path
from typing import Callable, Awaitable, Union

import imapclient

from email_config import AppConfig, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

IDLE_TIMEOUT = 25 * 60
RECONNECT_WAIT = 10


def make_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for raw, charset in parts:
        if isinstance(raw, bytes):
            result.append(raw.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(raw)
    return "".join(result)


def connect(config: AppConfig):
    email_cfg = config.email
    log.info("连接 %s:%s ...", email_cfg.imap_host, email_cfg.imap_port)
    client = imapclient.IMAPClient(
        email_cfg.imap_host, port=email_cfg.imap_port, ssl=True, ssl_context=make_ssl_context()
    )
    client.login(email_cfg.username, email_cfg.password)
    log.info("登录成功")

    client.select_folder(email_cfg.mailbox)
    existing = set(client.search(["ALL"]))
    log.info("当前收件箱共 %d 封邮件，开始监听新邮件...", len(existing))
    return client, existing


def fetch_and_process(
    client,
    msg_ids,
    on_new_email: Callable[[str, str, str], Union[Awaitable[None], None]],
):
    if not msg_ids:
        return
    log.info("拉取 %d 封新邮件: %s", len(msg_ids), msg_ids)
    raw_messages = client.fetch(msg_ids, ["RFC822"])
    for uid, data in raw_messages.items():
        raw = data[b"RFC822"]
        msg = email.message_from_bytes(raw)

        subject = decode_str(msg.get("Subject", "（无主题）"))
        sender = decode_str(msg.get("From", ""))
        date = msg.get("Date", "")

        print("\n" + "=" * 60)
        print(f"  UID    : {uid}")
        print(f"  时间   : {date}")
        print(f"  发件人 : {sender}")
        print(f"  主题   : {subject}")
        print("=" * 60)

        result = on_new_email(subject, sender, date)
        if hasattr(result, "__await__"):
            import asyncio
            asyncio.run(result)


def listen(
    config: AppConfig,
    on_new_email: Callable[[str, str, str], Union[Awaitable[None], None]],
):
    client, known_uids = connect(config)

    while True:
        try:
            log.info("进入 IDLE 模式（超时 %d 分钟）", IDLE_TIMEOUT // 60)
            client.idle()
            responses = client.idle_check(timeout=IDLE_TIMEOUT)
            client.idle_done()

            if responses:
                log.info("收到服务器推送: %s", responses)
                current_uids = set(client.search(["ALL"]))
                new_uids = current_uids - known_uids
                if new_uids:
                    fetch_and_process(client, list(new_uids), on_new_email)
                    known_uids = current_uids
                else:
                    log.info("推送为状态变更（非新邮件），忽略")
            else:
                log.debug("IDLE 超时，重新进入...")

        except KeyboardInterrupt:
            log.info("手动退出")
            client.logout()
            break

        except Exception as e:
            log.warning("连接异常: %s，%d 秒后重连...", e, RECONNECT_WAIT)
            try:
                client.logout()
            except Exception:
                pass
            time.sleep(RECONNECT_WAIT)
            client, known_uids = connect(config)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Email listener with SCM download trigger")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    args = parser.parse_args()

    config = load_config(args.config)

    def on_email(subject: str, sender: str, date: str):
        log.info("新邮件到达，准备触发 SCM 下载...")
        from run_send_record_downloads import run as scm_run
        import asyncio
        asyncio.run(scm_run(
            username=config.scm.username,
            password=config.scm.password,
            download_root=Path("artifacts/send-record-downloads"),
            headless=True,
            limit=None,
        ))
        log.info("SCM 下载流程完成")

    listen(config, on_email)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 3：验证语法**

运行: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m py_compile scripts/email_listener.py scripts/email_config.py`

预期: 无输出

- [ ] **步骤 4：运行所有测试验证无破坏**

运行: `cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ -q`

预期: 所有测试通过

- [ ] **步骤 5：提交**

```bash
git add scripts/email_listener.py
git commit -m "refactor: move email_listener to scripts and add callback support"
```

### 任务 3：更新 SKILL.md 添加首次使用说明

**涉及文件：**
- 修改: `SKILL.md`

- [ ] **步骤 1：添加首次使用配置章节**

在 `SKILL.md` 的"概述"章节之后、"适用场景"章节之前添加以下内容：

```markdown
## 首次使用配置

首次使用前，需要创建 `config.json` 配置文件。系统会读取该文件获取邮件监听凭据。

1. 复制示例配置：
   ```bash
   cp config.json.example config.json
   ```

2. 编辑 `config.json`，填入你的邮件账号密码：
   ```json
   {
     "email": {
       "imap_host": "imap.tinno.com",
       "imap_port": 993,
       "username": "你的邮箱@tinno.com",
       "password": "你的邮箱密码",
       "mailbox": "INBOX"
     }
   }
   ```

3. SCM 登录凭据已预设默认值（`TNProject01`/`Tinno@2030`），如需修改可在 `scm` 字段覆盖：
   ```json
   {
     "scm": {
       "username": "自定义账号",
       "password": "自定义密码"
     }
   }
   ```

4. 运行邮件监听（收到新邮件自动触发 SCM 下载）：
   ```bash
   python3 scripts/email_listener.py --config config.json
   ```

> **注意：** `config.json` 包含敏感凭据，已加入 `.gitignore`，不会被提交到仓库。
```

同时更新目录结构章节，添加 `email_config.py`、`email_listener.py` 和 `config.json.example`。

- [ ] **步骤 2：提交**

```bash
git add SKILL.md
git commit -m "docs: add first-time setup instructions to SKILL.md"
```

### 任务 4：更新 CHANGELOG 和 Gitignore

**涉及文件：**
- 修改: `CHANGELOG.md`
- 修改: `.gitignore`

- [ ] **步骤 1：添加 .gitignore 条目**

追加到 `.gitignore`：
```
config.json
```

- [ ] **步骤 2：更新 CHANGELOG.md**

追加到 `CHANGELOG.md`：

```markdown

## [0.3.0] - 2026-05-17

### 新增

- **email_listener.py** — 邮件监听触发 SCM 下载
  - 新邮件到达时自动运行完整的登录 → 供方发放 → 下载附件流程
  - 支持回调钩子，可扩展为自定义处理
- **email_config.py** — JSON 配置加载器
  - 邮件凭据从 `config.json` 读取（首次使用需配置）
  - SCM 凭据有默认值，可选覆盖
- **config.json.example** — 配置文件模板

### 变更

- `email_listener.py` 从项目根目录移至 `scripts/` 目录
```

- [ ] **步骤 3：提交**

```bash
git add .gitignore CHANGELOG.md
git commit -m "chore: update gitignore and changelog for email-triggered downloads"
```

### 任务 5：端到端验证

- [ ] **步骤 1：从示例创建 config.json**

```bash
cp config.json.example config.json
# 编辑 config.json 填入真实邮件凭据
```

- [ ] **步骤 2：运行所有测试**

```bash
cd /Users/shenmingjie/tinno/email-listen && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ -q
```

预期: 所有测试通过

- [ ] **步骤 3：验证邮件监听启动正常**

```bash
cd /Users/shenmingjie/tinno/email-listen && timeout 10 /opt/anaconda3/envs/py311/bin/python3 scripts/email_listener.py --config config.json || true
```

预期: 连接 IMAP，进入 IDLE 模式（然后超时终止）

## 自查清单

- 需求覆盖：
  - 监听收件人 `mingjie.shen@tinno.com` 的邮件 → 任务 2（listen 函数从配置读取邮件账号）
  - 收到邮件后触发 SCM 下载流程 → 任务 2（on_email 回调调用 scm_run）
  - 首次使用需要配置邮件凭据 → 任务 1（配置加载器）+ 任务 3（SKILL.md 配置说明）
  - SCM 登录账号密码固定 → 任务 1（email_config.py 中的 SCM 默认值）
  - JSON 配置格式 → 任务 1（load_config 读取 JSON）
  - config.json.example 模板 → 任务 1

- 占位符检查：未发现 TBD/TODO

- 类型一致性：
  - `AppConfig`、`EmailConfig`、`ScmConfig` 在各任务中一致使用
  - `load_config(path: Path) -> AppConfig` 签名在测试和实现中匹配
  - `on_new_email` 回调签名 `(subject, sender, date)` 一致
