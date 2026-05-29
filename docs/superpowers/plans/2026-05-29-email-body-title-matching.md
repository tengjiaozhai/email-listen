# 邮件正文标题匹配 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收到触发邮件后，从邮件 body 提取"内容"字段作为标题，在 SCM 未签收列表中找到标题完全匹配的那一条记录并下载，其余记录跳过；若解析不出内容字段或找不到匹配记录，则跳过本次 SCM 流程。

**Architecture:** 在 `email_listener.py` 的 `fetch_and_process` 中解析邮件 body 提取 `内容:` 字段，将 `title_filter` 字符串透传至 `run_send_record_downloads.run()`；`run()` 在选取记录前用 `matches_title_filter()` 做精确标题过滤；`scm_send_models.py` 新增该纯函数。

**Tech Stack:** Python 3.11, imapclient, Playwright, pytest

---

## 文件变更清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `scripts/scm_send_models.py` | 修改 | 新增 `matches_title_filter(row, title_filter)` 纯函数 |
| `scripts/email_listener.py` | 修改 | 新增 `extract_title_filter_from_body()`；`fetch_and_process` 解析 body；回调改为 4 参数 |
| `scripts/run_send_record_downloads.py` | 修改 | `run()` 增加 `title_filter` 参数，循环内用 `matches_title_filter` 过滤 |
| `tests/test_scm_send_models.py` | 修改 | 新增 `matches_title_filter` 测试 |
| `tests/test_email_listener.py` | 修改 | 新增 body 解析测试；更新旧测试回调签名 |
| `tests/test_run_send_record_downloads.py` | 修改 | 新增 title_filter 过滤行为测试 |

---
### Task 1: `scm_send_models.py` — 新增 `matches_title_filter`

**Files:**
- Modify: `scripts/scm_send_models.py`
- Test: `tests/test_scm_send_models.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_scm_send_models.py` 末尾追加：

```python
from scripts.scm_send_models import matches_title_filter

def test_matches_title_filter_exact_match():
    row = SendRecordRow(send_number="5001", serial_id="11",
                        title="P615F03 Z2581 生产技术通知单20260520",
                        sender="u1", sent_at="2026-05-21")
    assert matches_title_filter(row, "P615F03 Z2581 生产技术通知单20260520") is True

def test_matches_title_filter_no_match():
    row = SendRecordRow(send_number="5002", serial_id="12",
                        title="其他标题", sender="u1", sent_at="2026-05-21")
    assert matches_title_filter(row, "P615F03 Z2581 生产技术通知单20260520") is False

def test_matches_title_filter_none_filter_always_matches():
    row = SendRecordRow(send_number="5003", serial_id="13",
                        title="任意标题", sender="u1", sent_at="2026-05-21")
    assert matches_title_filter(row, None) is True
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/shenmingjie/tinno/email-listen
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_send_models.py::test_matches_title_filter_exact_match -v 2>&1 | head -c 2000
```

预期：`ERROR` 或 `ImportError`（函数未定义）

- [ ] **Step 3: 在 `scm_send_models.py` 末尾添加函数**

在文件末尾追加：

```python

def matches_title_filter(row: "SendRecordRow", title_filter: "str | None") -> bool:
    """title_filter 为 None 时匹配所有行；否则要求 row.title 与 title_filter 精确相等。"""
    if title_filter is None:
        return True
    return row.title == title_filter
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /Users/shenmingjie/tinno/email-listen
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_scm_send_models.py -v 2>&1 | head -c 2000
```

预期：全部 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/tinno/email-listen
git add scripts/scm_send_models.py tests/test_scm_send_models.py
git commit -m "feat: add matches_title_filter to scm_send_models"
```

---

### Task 2: `email_listener.py` — 解析邮件 body 提取 `title_filter`

**Files:**
- Modify: `scripts/email_listener.py`
- Test: `tests/test_email_listener.py`

邮件 body 格式（纯文本，每行 key:value）：
```
发放人:cui.lichao@zte.com.cn
收件人:ZTE.Tinno@tinno.com
发放时间:2026-05-21 19:46:23
下载权限截止日期:2026-06-10
内容:P615F03 Z2581 nubia A57 整机生产技术通知单20260520
```

- [ ] **Step 1: 在 `tests/test_email_listener.py` 末尾追加新测试**

```python
def test_extract_title_filter_standard_format():
    from email_listener import extract_title_filter_from_body
    body = (
        "发放人:cui.lichao@zte.com.cn\n"
        "收件人:ZTE.Tinno@tinno.com\n"
        "发放时间:2026-05-21 19:46:23\n"
        "内容:P615F03 Z2581 生产技术通知单20260520"
    )
    assert extract_title_filter_from_body(body) == "P615F03 Z2581 生产技术通知单20260520"


def test_extract_title_filter_missing_field():
    from email_listener import extract_title_filter_from_body
    body = "发放人:someone@zte.com.cn\n收件人:ZTE.Tinno@tinno.com"
    assert extract_title_filter_from_body(body) is None


def test_extract_title_filter_empty_string():
    from email_listener import extract_title_filter_from_body
    assert extract_title_filter_from_body("") is None


def test_extract_title_filter_strips_whitespace():
    from email_listener import extract_title_filter_from_body
    body = "内容:  P615F03 Z2581  "
    assert extract_title_filter_from_body(body) == "P615F03 Z2581"


def test_fetch_and_process_extracts_title_and_passes_to_callback():
    from email_listener import fetch_and_process
    body = "发放人:cui.lichao@zte.com.cn\n内容:P615F03 生产技术通知单20260520"
    msg = _build_email_with_body(
        to="ZTE.Tinno@tinno.com",
        sender="cui.lichao@zte.com.cn",
        subject="发放通知",
        body=body,
    )
    client = _FakeClient(msg.as_bytes())
    config = _make_config(trigger_recipients=["zte.tinno@tinno.com"])
    called = []

    def on_new_email(subject, sender, date, title_filter):
        called.append(title_filter)

    fetch_and_process(client, [103], on_new_email, config)
    assert called == ["P615F03 生产技术通知单20260520"]


def test_fetch_and_process_skips_when_body_has_no_content_field():
    from email_listener import fetch_and_process
    msg = _build_email_with_body(
        to="ZTE.Tinno@tinno.com",
        sender="cui.lichao@zte.com.cn",
        subject="发放通知",
        body="发放人:cui.lichao@zte.com.cn",
    )
    client = _FakeClient(msg.as_bytes())
    config = _make_config(trigger_recipients=["zte.tinno@tinno.com"])
    called = []

    def on_new_email(subject, sender, date, title_filter):
        called.append(title_filter)

    fetch_and_process(client, [104], on_new_email, config)
    assert called == []


def _build_email_with_body(to, sender, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg["Date"] = "Tue, 19 May 2026 12:00:00 +0800"
    msg.set_content(body)
    return msg
```

同时更新已有的旧测试中的 `_build_email` 和 `on_new_email`：

`_build_email` 增加默认 body 参数（让旧测试里的邮件带有 `内容:` 字段，否则 title_filter 为 None 会被 continue 跳过，导致回调不触发）：
```python
def _build_email(to: str, sender: str, subject: str, body: str = "内容:测试标题") -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg["Date"] = "Tue, 19 May 2026 12:00:00 +0800"
    msg.set_content(body)
    return msg
```

旧测试中的两处 `on_new_email` 签名改为接收 4 个参数：
```python
def on_new_email(subject: str, sender: str, date: str, title_filter):
    called.append((subject, sender, date))
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/shenmingjie/tinno/email-listen
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_email_listener.py::test_extract_title_filter_standard_format -v 2>&1 | head -c 2000
```

预期：`ImportError`（函数未定义）

- [ ] **Step 3: 在 `email_listener.py` 的 `should_trigger` 函数之前（第 53 行前）插入**

```python
def extract_title_filter_from_body(body: str) -> "str | None":
    """从邮件正文中提取 '内容:' 字段的值。

    正文每行格式为 key:value，提取 '内容' 对应的值并 strip。
    找不到或值为空时返回 None。
    """
    for line in body.splitlines():
        if line.startswith("内容:"):
            value = line[len("内容:"):].strip()
            return value if value else None
    return None
```

- [ ] **Step 4: 修改 `fetch_and_process` — 解析 body、跳过逻辑、更新回调调用**

在 `email_listener.py` 的 `fetch_and_process` 函数中，将第 103-129 行修改为：

```python
        subject = decode_str(msg.get("Subject", "（无主题）"))
        sender = decode_str(msg.get("From", ""))
        date = msg.get("Date", "")
        recipient_fields = ", ".join(
            filter(
                None,
                [
                    decode_str(msg.get("To", "")),
                    decode_str(msg.get("Cc", "")),
                    decode_str(msg.get("Delivered-To", "")),
                    decode_str(msg.get("X-Original-To", "")),
                ],
            )
        )

        if not should_trigger(recipient_fields, config):
            log.info("UID=%s 收件人不在 trigger_recipients 中，跳过触发", uid)
            continue

        # 解析邮件正文
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get_content_disposition():
                    charset = part.get_content_charset() or "utf-8"
                    body_text = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
        else:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                body_text = payload.decode(charset, errors="replace")

        title_filter = extract_title_filter_from_body(body_text)
        if title_filter is None:
            log.warning("UID=%s 邮件正文未找到「内容」字段，跳过本次 SCM 流程", uid)
            continue

        print("\n" + "=" * 60)
        print(f"  UID    : {uid}")
        print(f"  时间   : {date}")
        print(f"  发件人 : {sender}")
        print(f"  主题   : {subject}")
        print(f"  标题   : {title_filter}")
        print("=" * 60)

        result = on_new_email(subject, sender, date, title_filter)
        if hasattr(result, "__await__"):
            import asyncio
            asyncio.run(result)
```

同时更新函数签名中的类型注解（第 92 行）：
```python
    on_new_email: Callable[[str, str, str, "str | None"], Union[Awaitable[None], None]],
```

- [ ] **Step 5: 运行确认通过**

```bash
cd /Users/shenmingjie/tinno/email-listen
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_email_listener.py -v 2>&1 | head -c 3000
```

预期：全部 PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/shenmingjie/tinno/email-listen
git add scripts/email_listener.py tests/test_email_listener.py
git commit -m "feat: parse email body to extract title_filter for SCM matching"
```

---

### Task 3: `run_send_record_downloads.py` — 接收 `title_filter` 并过滤记录

**Files:**
- Modify: `scripts/run_send_record_downloads.py`
- Modify: `scripts/email_listener.py` (on_email 回调)
- Test: `tests/test_run_send_record_downloads.py`

- [ ] **Step 1: 在 `tests/test_run_send_record_downloads.py` 末尾追加测试**

```python
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
```

- [ ] **Step 2: 运行确认通过**

```bash
cd /Users/shenmingjie/tinno/email-listen
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_run_send_record_downloads.py -v 2>&1 | head -c 2000
```

预期：PASS（测试只依赖 model 函数，已在 Task 1 实现）

- [ ] **Step 3: 修改 `run()` 函数签名，增加 `title_filter` 参数**

将 `scripts/run_send_record_downloads.py` 第 33 行改为：

```python
async def run(username: str, password: str, download_root: Path, headless: bool, limit: int | None, webhook: str, title_filter: str | None = None) -> None:
```

- [ ] **Step 4: 在 `run()` 顶部 import 处加入 `matches_title_filter`**

将第 17 行：
```python
from scm_send_models import choose_next_unprocessed
```
改为：
```python
from scm_send_models import choose_next_unprocessed, matches_title_filter
```

- [ ] **Step 5: 修改 while 循环中的记录选取逻辑**

将 `run()` 中的 while 循环（第 51-58 行）改为：

```python
            while True:
                rows = await read_send_rows(right)
                if not rows or should_stop(rows, processed):
                    break

                eligible = [r for r in rows if matches_title_filter(r, title_filter)]
                if not eligible:
                    log.warning("SCM 列表中无标题匹配 %r 的未签收记录，跳过本次下载", title_filter)
                    break

                row = choose_next_unprocessed(eligible, processed)
                if row is None:
                    break
```

- [ ] **Step 6: 修改 `email_listener.py` 的 `on_email` 回调，接收并传递 `title_filter`**

将 `scripts/email_listener.py` 的 `main()` 中 `on_email` 函数（第 183-195 行）改为：

```python
    def on_email(subject: str, sender: str, date: str, title_filter: str | None):
        log.info("新邮件到达，标题过滤条件: %r，准备触发 SCM 下载...", title_filter)
        from run_send_record_downloads import run as scm_run
        import asyncio
        asyncio.run(scm_run(
            username=config.scm.username,
            password=config.scm.password,
            download_root=Path("artifacts"),
            headless=True,
            limit=None,
            webhook=config.wecom.webhook,
            title_filter=title_filter,
        ))
        log.info("SCM 下载流程完成")
```

- [ ] **Step 7: 运行全部测试**

```bash
cd /Users/shenmingjie/tinno/email-listen
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ -v 2>&1 | head -c 4000
```

预期：全部 PASS

- [ ] **Step 8: Commit**

```bash
cd /Users/shenmingjie/tinno/email-listen
git add scripts/run_send_record_downloads.py scripts/email_listener.py tests/test_run_send_record_downloads.py
git commit -m "feat: filter SCM records by title extracted from email body"
```

---

## 自检结果

| 需求 | 覆盖 Task |
|---|---|
| 从邮件 body 提取"内容"字段 | Task 2: `extract_title_filter_from_body` |
| 与 SCM 发放标题精确匹配 | Task 1: `matches_title_filter` + Task 3: eligible 过滤 |
| body 无内容字段时跳过 SCM 流程 | Task 2: `continue` + `log.warning` |
| SCM 列表无匹配时跳过 | Task 3: `break` + `log.warning` |
| `title_filter=None` 时下载全部（向后兼容） | Task 1: `matches_title_filter(row, None) -> True` |
| 旧测试不破坏 | Task 2 Step 1: 更新旧测试签名和 `_build_email` |
