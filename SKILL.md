# ZTE SCM 滑块验证码自动化 Skill

## 概述

自动化 ZTE SCM 供应链管理平台的滑块验证码登录流程。采用 Python Playwright + 纯 OpenCV 方案，拦截 jigsaw API 返回的图像数据，通过模板匹配定位缺口坐标，执行拟人化拖动。

## 适用场景

- ZTE SCM 供应链平台自动化登录
- 滑块验证码 (jigsaw) 的图像求解
- 需要绕过 UAC 统一认证的滑块验证

## 目录结构

```
email-listen/
├── scripts/
│   ├── slider_solver.py          # 纯 OpenCV 滑块求解器
│   └── zte_scm_slider_poc.py     # Playwright 自动化主流程
├── tests/
│   ├── conftest.py               # pytest 路径配置
│   └── test_slider_solver.py     # 求解器单元测试
├── docs/
│   ├── PLAN.md                   # 实施计划
│   └── research.md               # 调研记录
├── artifacts/
│   ├── slider-poc/               # 运行时调试产物
│   └── jigsaw_response.json      # 示例响应数据
├── CHANGELOG.md                  # 版本记录
└── SKILL.md                      # 本文件
```

## 核心模块

### slider_solver.py

纯图像求解模块，不依赖 Playwright。

```python
from slider_solver import solve_slider, SliderSolution

solution = solve_slider(big_img_data_url, small_img_data_url, y_height=62, panel_width=280)
# solution.target_x      → 缺口 x 坐标
# solution.drag_distance  → 拖动距离
# solution.confidence     → 匹配置信度 [0, 1]
```

### zte_scm_slider_poc.py

完整自动化流程脚本。

```bash
python3 scripts/zte_scm_slider_poc.py --username TNProject01 --password TNProject01
# 或通过环境变量
ZTE_USERNAME=xxx ZTE_PASSWORD=xxx python3 scripts/zte_scm_slider_poc.py
```

## 流程说明

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

## 调试产物

每次运行输出到 `artifacts/slider-poc/<timestamp>/`：

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
