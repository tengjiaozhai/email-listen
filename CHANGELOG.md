# 版本记录 (CHANGELOG)

本文件记录每次版本的变更内容。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [0.1.0] - 2026-05-16

### 新增

- **slider_solver.py** — 纯 OpenCV 滑块求解器
  - `solve_slider()` 接口：解码 data URL → alpha 裁剪模板 → 局部模板匹配 → 返回 `SliderSolution`
  - `SliderSolution` 数据类：含 `target_x`、`target_y`、`piece_initial_x`、`drag_distance`、`confidence`
  - `draw_overlay()` 调试可视化：绘制目标框、拖动箭头、参数标注

- **zte_scm_slider_poc.py** — Playwright 完整自动化流程
  - 入口页：勾选隐私政策 → 点登录 → 跳转 UAC
  - UAC 登录：用户名/密码填写，密码框 click 解除 readonly
  - jigsaw 拦截：监听 `/srv/kaptcha/jigsaw` 响应，提取 `bigImg`/`smallImg`/`yHeight`
  - 拟人拖动：ease-out cubic 曲线，25-35 步，350-600ms，纵向抖动 ±1.5px，overshoot+settle
  - 重试机制：最多 3 次，优先点刷新图标，fallback 关闭弹窗重登
  - 调试产物：7 类文件输出到 `artifacts/slider-poc/<timestamp>/`

- **test_slider_solver.py** — 8 个测试用例
  - 合成图像测试（模拟拼图切割）+ 真实 `jigsaw_response.json` 集成测试
  - 覆盖：字段完整性、坐标边界、拖动距离、置信度阈值、data URL 解码、alpha 裁剪

- **项目结构重组**
  - `scripts/` — 存放可执行脚本
  - `tests/` — 存放测试代码
  - `docs/` — 存放文档（PLAN.md、research.md）
  - `SKILL.md` — Skill 说明文档

### 调研结论

- ZTE SCM 使用 Microsoft Exchange IMAP4 邮件服务（`imap.tinno.com:993`，SSL/TLS，AUTH=PLAIN）
- 滑块验证码通过 `/srv/kaptcha/jigsaw` 接口返回 `bigImg`（背景图）、`smallImg`（拼图块）、`yHeight`（y 坐标）
- 纯 OpenCV 模板匹配在合成数据和真实数据上均可正确定位缺口

---

## [未发布]

_以下版本待后续迭代更新。_

## [0.2.0] - 2026-05-17

### 新增

- **scm_auth.py** — 可复用登录模块，从 zte_scm_slider_poc.py 提取
- **scm_send_pages.py** — 框架感知页面对象（供方管理 → 供方发放导航）
- **scm_send_models.py** — 发放记录数据模型和纯辅助函数
- **scm_send_worker.py** — 下载工人，处理附件下载和清单生成
- **run_send_record_downloads.py** — 端到端 CLI 工作流
- 供方发放自动化：筛选未签收记录 → 打开详情 → 下载生产技术通知单 → 返回列表继续
