# Download Root to CWD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `download_root` 默认值从 `artifacts/send-record-downloads` 改为 `Path(".")`，即当前工作目录根，使下载产物直接落在运行命令的目录下。

**Architecture:** 修改两处硬编码默认路径（CLI 参数默认值 + 邮件监听触发调用），同步更新 SKILL.md 文档描述。无需新增抽象，属于纯配置值替换。

**Tech Stack:** Python 3.11, imapclient, playwright, pytest

---

### Task 1: 修改 CLI 默认 download-root

**Files:**
- Modify: `scripts/run_send_record_downloads.py:83`

- [ ] **Step 1: 修改 `--download-root` 默认值**

将 `scripts/run_send_record_downloads.py` 第 83 行从：

```python
parser.add_argument("--download-root", type=Path, default=Path("artifacts/send-record-downloads"))
```

改为：

```python
parser.add_argument("--download-root", type=Path, default=Path("."))
```

- [ ] **Step 2: 验证语法正确**

```bash
python3 -c "from scripts.run_send_record_downloads import build_run_root; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 运行已有测试确保不破坏**

```bash
python3 -m pytest tests/test_run_send_record_downloads.py -v
```

Expected: `PASSED tests/test_run_send_record_downloads.py::test_build_run_root_places_timestamp_under_download_root`

- [ ] **Step 4: Commit**

```bash
git add scripts/run_send_record_downloads.py
git commit -m "feat: change default download-root to cwd (.)"
```

---

### Task 2: 修改邮件监听触发时的 download_root

**Files:**
- Modify: `scripts/email_listener.py:190`

- [ ] **Step 1: 修改 `email_listener.py` 中的 download_root 调用**

将 `scripts/email_listener.py` 第 190 行从：

```python
download_root=Path("artifacts/send-record-downloads"),
```

改为：

```python
download_root=Path("."),
```

- [ ] **Step 2: 验证语法正确**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from email_listener import listen
print('OK')
"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/email_listener.py
git commit -m "feat: email listener uses cwd as download root"
```

---

### Task 3: 更新 SKILL.md 下载目录文档

**Files:**
- Modify: `SKILL.md` — 下载目录章节

- [ ] **Step 1: 更新 SKILL.md 下载目录描述**

找到 `SKILL.md` 中的"下载目录"章节，将：

```markdown
**所有下载文件固定存放在 `artifacts/send-record-downloads/` 目录下**，目录结构：
```

替换为：

```markdown
**所有下载文件默认存放在运行命令时的当前工作目录（cwd）下**，目录结构：
```

并将目录示例从：

```
artifacts/send-record-downloads/
└── <时间戳>/
```

替换为：

```
<cwd>/
└── <时间戳>/
```

并在示例后补充：

```markdown
也可以通过 `--download-root` 参数指定其他目录：

```bash
python3 scripts/run_send_record_downloads.py --download-root /path/to/dir ...
```
```

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "docs: update download directory description to cwd default"
```
