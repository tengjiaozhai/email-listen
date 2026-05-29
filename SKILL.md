---
name: zte-scm-slider-captcha
version: "1.1.0"
license: "MIT"
description: "ZTE SCM 供应链平台自动化登录与发放单下载。当用户提到 ZTE SCM、滑块验证码、供应链平台登录、发放单下载、生产技术通知单下载时触发此技能。支持邮件监听自动触发和手动 CLI 两种模式。"
triggers:
  - "ZTE SCM"
  - "滑块验证码"
  - "供应链平台"
  - "发放单下载"
  - "生产技术通知单"
  - "jigsaw captcha"
  - "未签收"
not_triggers:
  - "下载其他平台附件"
  - "邮件内容分析"
  - "非 ZTE SCM 登录"
---

# ZTE SCM 供应链自动化 Skill

## 概述

自动化 ZTE SCM 供应链管理平台的登录和发放单下载流程。采用 Python Playwright + 纯 OpenCV 方案，拦截 jigsaw API 返回的图像数据，通过模板匹配定位缺口坐标，执行拟人化拖动，完成后自动进入供方发放页面筛选未签收记录并下载附件。

## 适用场景与禁用场景

### 适用场景（MUST USE）

| 场景 | 说明 |
|---|---|
| 需要登录 ZTE SCM 供应链平台 | 含滑块验证码自动求解 |
| 下载 ZTE 供方发放的生产技术通知单 | 针对未签收记录批量下载 |
| 配置邮件自动触发 SCM 下载 | IMAP IDLE 监听 + 自动触发 |
| 调试 ZTE jigsaw 滑块验证码 | OpenCV 模板匹配求解 |

### 禁用场景（MUST NOT USE）

| 场景 | 替代方案 |
|---|---|
| 非 ZTE SCM 平台的登录 | 使用对应平台的 skill |
| 下载非生产技术通知单的附件 | 手动操作或其他 skill |
| 一般邮件内容分析 / 邮件分类 | 使用通用邮件处理 skill |
| 其他供应链平台（非 supply.zte.com.cn） | 使用对应平台的 skill |
| 已签收记录的重复下载 | 直接进入 SCM 手动操作 |

> **判断规则：** 如果目标 URL 不含 `supply.zte.com.cn`，不要使用本 skill。

## 触发方式选择

当用户提到"发放单下载"、"下载附件"、"未签收"等关键词时，根据用户意图选择不同模式：

| 用户说法 | 触发模式 | 执行命令 |
|----------|----------|----------|
| "帮我下载发放单" / "下载未签收附件" | **立即执行一次** | `run_send_record_downloads.py` CLI |
| "启动邮件监听" / "配置自动下载" | **启动持续监听** | `email_listener.py` |
| "配置邮件触发" / "设置收件人" | **引导配置** | 编辑 `config.json` |

**判断规则：**
- 用户说"帮我下载"、"下载一下"、"获取发放单" → **立即执行 CLI**，不启动监听
- 用户说"监听"、"自动触发"、"邮件来了自动下载" → **启动邮件监听**
- 用户说"配置"、"设置"、"添加收件人" → **引导编辑 config.json**

> **重要：** `trigger_recipients` 默认监听 `ZTE.Tinno@tinno.com`，用户可自定义修改。

## 环境检查（首次运行前必检）

**在执行任何操作之前，必须先检查运行环境。** 缺少依赖会导致运行时崩溃。

### 检查命令

```bash
# 1. 检查 Python 版本（需要 >= 3.11）
python3 --version

# 2. 检查依赖包是否安装
python3 -c "import cv2, numpy, playwright, imapclient; print('All dependencies OK')"

# 3. 检查 Playwright 浏览器是否安装
python3 -m playwright install --dry-run 2>&1 | grep -q "chromium" || python3 -m playwright install chromium

# 4. 检查 config.json 是否存在
test -f config.json && echo "config.json exists" || echo "config.json missing - need to create"
```

### 依赖清单

| 依赖 | 用途 | 安装命令 |
|------|------|----------|
| Python >= 3.11 | 运行环境 | — |
| opencv-python | 滑块图像模板匹配 | `pip install opencv-python` |
| numpy | 图像数组处理 | `pip install numpy` |
| playwright | 浏览器自动化 | `pip install playwright` |
| playwright chromium | 浏览器引擎 | `python3 -m playwright install chromium` |
| imapclient | IMAP 邮件监听 | `pip install imapclient` |
| pytest | 运行测试 | `pip install pytest` |

### 一键安装

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
```

### 自动安装

**首次运行前，系统会自动检测并安装缺失依赖，无需用户手动操作。**

自动安装流程：

1. 检测 Python 环境和版本：
   - 若未检测到 Python（如 `python3: command not found`），提示用户先安装 Python 3.11+
   - macOS：可用 Homebrew 安装 `brew install python@3.11`，或从 python.org 下载官方安装包
   - Windows：可从 python.org 下载官方安装包（安装时勾选 Add python.exe to PATH），或使用 `winget install Python.Python.3.11`
   - 若版本 < 3.11，则报错提示用户手动升级
2. 检测 `requirements.txt` 中的包，缺失的自动 `pip install`
3. 检测 Playwright 浏览器，未安装则自动 `python3 -m playwright install chromium`
4. 检测 `config.json`，不存在则自动从 `config.json.example` 复制并提示用户填写凭据

```bash
# 自动安装脚本（在执行主逻辑前运行）
python3 -c "
import subprocess, sys, shutil
from pathlib import Path

# 1. 安装 Python 依赖
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'])

# 2. 安装 Playwright chromium
subprocess.check_call([sys.executable, '-m', 'playwright', 'install', 'chromium'])

# 3. 检查 config.json
if not Path('config.json').exists():
    if Path('config.json.example').exists():
        shutil.copy('config.json.example', 'config.json')
        print('已创建 config.json，请填写邮箱密码后重新运行')
        sys.exit(1)
    else:
        print('缺少 config.json 和 config.json.example')
        sys.exit(1)

print('环境检查通过')
"
```

> **约束：** 自动安装仅处理 pip 包和 Playwright 浏览器。Python 安装/版本与 config.json 凭据需用户手动处理。

### 检查失败处理

| 检查项 | 失败表现 | 修复方式 |
|--------|----------|----------|
| Python 环境 | `python3: command not found` / `No such file or directory` | 先安装 Python 3.11+：macOS 用 `brew install python@3.11`（或 python.org 安装包）；Windows 用 python.org 安装包（勾选 Add python.exe to PATH）或 `winget install Python.Python.3.11` |
| Python 版本 | 版本 < 3.11 | 安装 Python 3.11+（需用户手动） |
| opencv-python | `ModuleNotFoundError: No module named 'cv2'` | 自动安装 `pip install opencv-python` |
| numpy | `ModuleNotFoundError: No module named 'numpy'` | 自动安装 `pip install numpy` |
| playwright | `ModuleNotFoundError: No module named 'playwright'` | 自动安装 `pip install playwright` |
| chromium 浏览器 | `Executable doesn't exist` | 自动安装 `python3 -m playwright install chromium` |
| imapclient | `ModuleNotFoundError: No module named 'imapclient'` | 自动安装 `pip install imapclient` |
| config.json | `Config file not found` | 自动从 `config.json.example` 复制，提示填写凭据 |

> **约束：** 如果任何检查失败且无法自动修复，必须先修复再继续。不要跳过检查直接运行。

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
       "mailbox": "INBOX",
        "trigger_recipients": ["ZTE.Tinno@tinno.com"]
     }
   }
   ```

   > **`trigger_recipients`（要监听的收件人）说明：**
   > - 默认值：`ZTE.Tinno@tinno.com`（ZTE 供应链通知邮箱）
   > - 配置需要触发 SCM 下载的收件人邮箱地址列表
   > - 支持多个收件人：`["ZTE.Tinno@tinno.com", "group@tinno.com"]`
   > - 支持群组邮箱：`["scm-group@tinno.com"]`
   > - 为空或不配置时，所有新邮件都会触发（向后兼容）
   > - **配置时机：** 当用户选择"邮件监听"模式时，可询问"要监听哪些收件人的邮件？默认为 ZTE.Tinno@tinno.com"

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

### config.json 字段规格

| 字段 | 类型 | 必填 | 格式/约束 | 示例值 |
|---|---|---|---|---|
| `email.imap_host` | string | 是 | 合法域名或 IP，不含协议头 | `"imap.tinno.com"` |
| `email.imap_port` | integer | 是 | 1-65535，IMAP over SSL 通常为 993 | `993` |
| `email.username` | string | 是 | 完整邮箱地址，含 `@` 域名 | `"user@tinno.com"` |
| `email.password` | string | 是 | 非空字符串，不做长度限制 | `"MyPass123"` |
| `email.mailbox` | string | 否 | IMAP 文件夹名称，默认 `"INBOX"` | `"INBOX"` |
| `email.trigger_recipients` | array of string | 否 | 每项须为合法邮箱地址；为空则所有邮件触发 | `["ZTE.Tinno@tinno.com"]` |
| `scm.username` | string | 否 | SCM 登录账号，默认 `"TNProject01"` | `"TNProject01"` |
| `scm.password` | string | 否 | SCM 登录密码，默认 `"Tinno@2030"` | `"Tinno@2030"` |
| `wecom.webhook` | string | 是 | 企业微信 Webhook 完整 URL，须含 `key=` 参数 | `"https://qyapi.weixin.qq.com/..."` |

**校验失败时的行为：**
- 缺少必填字段 → `ConfigError` 异常，输出缺失字段名，程序退出
- `imap_port` 非整数 → JSON 解析阶段报错
- `trigger_recipients` 含非邮箱格式字符串 → 不报错，但 IMAP 匹配始终失败（静默跳过）
- `wecom.webhook` 为空字符串 → `ConfigError: Missing wecom.webhook in config`

> **注意：** `config.json` 包含敏感凭据，已加入 `.gitignore`，不会被提交到仓库。

## 适用场景

- ZTE SCM 供应链平台自动化登录
- 滑块验证码 (jigsaw) 的图像求解
- 需要绕过 UAC 统一认证的滑块验证
- 供方发放未签收记录的批量下载

## 目录结构

```
email-listen/
├── scripts/
│   ├── slider_solver.py              # 纯 OpenCV 滑块求解器
│   ├── scm_auth.py                   # 可复用登录模块（滑块验证码 + 进入系统）
│   ├── scm_send_pages.py             # 框架感知页面对象（供方发放导航 + 列表/详情）
│   ├── scm_send_models.py            # 数据模型和纯辅助函数
│   ├── scm_send_worker.py            # 下载工人（附件下载 + 清单生成）
│   ├── run_send_record_downloads.py  # 端到端 CLI 工作流
│   ├── zte_scm_slider_poc.py         # 滑块验证 PoC（独立调试用）
│   ├── email_config.py               # 邮件配置加载模块
│   └── email_listener.py             # 邮件监听入口（IMAP IDLE）
├── tests/
│   ├── conftest.py                   # pytest 路径配置
│   ├── test_slider_solver.py         # 求解器单元测试
│   ├── test_scm_auth_urls.py         # URL 匹配测试
│   ├── test_scm_send_pages.py        # 页面对象测试
│   ├── test_scm_send_models.py       # 模型和辅助函数测试
│   ├── test_scm_send_worker.py       # 下载工人测试
│   └── test_run_send_record_downloads.py  # CLI 辅助函数测试
├── docs/
│   ├── PLAN.md                       # 实施计划
│   └── research.md                   # 调研记录
├── artifacts/
│   ├── slider-poc/                   # 滑块验证调试产物
│   ├── send-record-downloads/        # 发放单下载文件存放目录（固定位置）
│   └── jigsaw_response.json          # 示例响应数据
├── CHANGELOG.md                      # 版本记录
├── config.json.example               # 配置文件模板
└── SKILL.md                          # 本文件
```

## 核心模块

### scm_auth.py — 登录模块

可复用登录流程，支持滑块验证码自动求解。

```python
from scm_auth import ScmCredentials, login_and_enter_system

credentials = ScmCredentials(username="TNProject01", password="xxx")
await login_and_enter_system(page, credentials, artifacts_dir=Path("artifacts"))
```

### run_send_record_downloads.py — 端到端下载

完整的发放单下载工作流 CLI。

```bash
python3 scripts/run_send_record_downloads.py \
  --username TNProject01 \
  --password 'Tinno@2030' \
  --headless \
  --limit 10
```

参数说明：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--username` | SCM 登录账号（必填） | — |
| `--password` | SCM 登录密码（必填） | — |
| `--headless` | 无头模式运行 | 否 |
| `--limit` | 最大下载记录数 | 无限制 |

## 下载目录

**所有下载文件默认存放在运行命令时的当前工作目录下的 `artifacts/` 子目录**，目录结构：

```
<cwd>/artifacts/
└── <时间戳>/                    # 例如 20260517_161001
    ├── uac_before_submit.png    # 登录截图
    ├── run.json                 # 运行清单（记录每条发放单的下载详情）
    └── <发放单号>/              # 例如 500005314623
        ├── download1__...7z     # 下载1（生产技术通知单）
        └── download2__...7z     # 下载2（生产技术通知单）
```

也可以通过 `--download-root` 参数指定其他目录：

```bash
python3 scripts/run_send_record_downloads.py --download-root /path/to/dir ...
```

`run.json` 格式：

```json
{
  "records": [
    {
      "send_number": "500005314623",
      "serial_id": "11363656",
      "title": "生产技术通知单...",
      "sender": "赵勇攀10015134",
      "sent_at": "2026-05-15",
      "downloads": {
        "dtg_AttachList__ctl3_Linkbutton1": "artifacts/send-record-downloads/.../download1__...7z",
        "dtg_AttachList__ctl3_Linkbutton2": "artifacts/send-record-downloads/.../download2__...7z"
      }
    }
  ]
}
```

## 流程说明

### 登录流程

1. 打开 ZTE SCM 入口页
2. 勾选隐私政策 `#chb_privacy_policy`
3. 点击登录 `#btn_login_cl` → 跳转 UAC
4. 填写用户名 `#input-loginname`
5. 点击密码框解除 `readonly`，填写密码 `#input-password`
6. 点击登录 `#btn-signin`
7. 拦截 `GET /srv/kaptcha/jigsaw` 响应
8. 解码 `bigImg` / `smallImg`，调用 `solve_slider()` 求解
9. 读取 DOM 计算 `piece_initial_x`（`block.left - sliderPanel.left`）
10. 执行拟人拖动（ease-out 曲线, 25-35 步, 350-600ms, overshoot+settle）
11. 验证成功 / 重试（最多 3 次）

### 下载流程

1. 登录后点击 `进入系统` → 进入 `Index.aspx?TYPE=0`
2. 顶部菜单 `news` frame 点击 `供方管理`
3. 左侧 `leftup` frame 展开 `供方发放` 菜单
4. 进入引导页 → 点击 `#ibtnEnter` → 进入列表页
5. 筛选 `未签收` 记录（`#ddlSignStatus` 选 `0`，点击 `#btnQuery`）
6. 循环处理每条记录：
   - 点击发放单编号打开详情页
   - 查找包含 `生产技术通知单` 的附件
   - 点击 `下载1` / `下载2` 保存文件
   - 点击 `#btnReturn` 返回列表
   - 重新查询未签收记录
7. 全部处理完毕后写入 `run.json`

## 调试产物

滑块验证调试产物输出到 `artifacts/slider-poc/<timestamp>/`：

| 文件 | 说明 |
|------|------|
| `uac_before_submit.png` | 登录前截图 |
| `jigsaw_dialog.png` | 验证码弹窗截图 |
| `jigsaw_raw.json` | jigsaw API 原始响应 |
| `big.png` | 背景图 |
| `small.png` | 拼图块 |
| `overlay.png` | 求解结果可视化 |
| `run.json` | 完整运行日志 |

## 运行测试

```bash
python3 -m pytest tests/ -v
```

## 依赖

- Python 3.11+
- opencv-python
- numpy
- playwright
