# ZTE SCM 滑块验证接口/CV PoC 计划

**摘要**

我正在使用 `writing-plans` skill 来创建实施计划。

本次调研按你已确认的路线执行：做一个**可运行 PoC**，主线采用 **Python Playwright + 纯 OpenCV**，不把 `tinno/output/img_gen.py` 作为主流程依赖。PoC 目标是从入口页进入 UAC 登录页，触发滑块验证码，直接消费 `/srv/kaptcha/jigsaw` 返回的 `bigImg`、`smallImg`、`yHeight`，求出缺口横坐标并执行拖动，保留完整调试产物。

**关键实现**

- 新建主入口脚本 `zte_scm_slider_poc.py`，负责完整流程编排。
  - 先打开 ZTE SCM 入口页。
  - 勾选 `#chb_privacy_policy`，再点击 `#btn_login_cl`。
  - 等待跳转到 UAC 登录页，等待策略统一用 `domcontentloaded` + 明确选择器等待，不使用 `networkidle`。
  - UAC 登录页固定使用：
    - 用户名输入框 `#input-loginname`
    - 密码输入框 `#input-password`
    - 登录按钮 `#btn-signin`
  - 密码框先 `click()` 解锁 `readonly`，再输入密码，不能直接 `fill()`。

- 新建 `slider_solver.py`，封装滑块求解逻辑。
  - 暴露接口：`solve_slider(big_img_data_url, small_img_data_url, y_height, panel_width) -> SliderSolution`
  - `SliderSolution` 至少包含：
    - `target_x`
    - `target_y`
    - `piece_initial_x`
    - `drag_distance`
    - `confidence`
  - 解码 `bigImg`、`smallImg` 的 data URL。
  - 以 `smallImg` alpha 区域裁出有效模板。
  - 先在 `y_height` 附近做局部搜索，再做模板匹配，优先保留分数最高且坐标落在图板范围内的结果。
  - 不硬编码 `280` 和 `20`；`target_x` 用图像匹配得出，`piece_initial_x` 用 DOM 位置实时计算。

- 主脚本登录后拦截验证码接口并驱动拖动。
  - 拦截 `GET /zte-bmt-ucs-portalbff/srv/kaptcha/jigsaw?kid=...`
  - 校验返回 `bo.bigImg`、`bo.smallImg`、`bo.yHeight`
  - 读取滑块相关 DOM：
    - `#sliderPanel`
    - `#bigImage`
    - `#block`
    - `#sliderContainer`
    - `#slider`
    - `#sliderMask`
  - 用 `block.left - sliderPanel.left` 计算 `piece_initial_x`
  - 用 `target_x - piece_initial_x` 计算最终 `drag_distance`
  - 用 `page.mouse` 执行拟人拖动：
    - 起点取 `#slider` 中心
    - 25 到 35 步 eased path
    - 总时长 350 到 600 ms
    - 允许轻微纵向抖动 1 到 3 px
    - 末尾做一次小幅 overshoot/settle，避免过于机械

- 失败重试逻辑固定为 3 次。
  - 首选点击弹窗内刷新图标 `.el-icon-refresh-right` 重新拉取验证码。
  - 如果刷新不可用或弹窗状态异常，关闭弹窗后重新点登录。
  - 每次重试都重新拦截新的 `jigsaw` 响应并重新求解，不复用上一次坐标。

- 调试产物统一输出到 `artifacts/slider-poc/<timestamp>/`。
  - 保存：
    - `uac_before_submit.png`
    - `jigsaw_dialog.png`
    - `jigsaw_raw.json`
    - `big.png`
    - `small.png`
    - `overlay.png`：本地绘制目标框、横坐标和拖动距离
    - `run.json`：记录接口参数、DOM bbox、匹配分数、拖动距离、结果状态
  - 在 [research.md](/Users/shenmingjie/tinno/email-listen/research.md) 追加调研结论与已验证事实，不写实现细节流水账。

**接口与边界**

- `zte_scm_slider_poc.py` 使用 CLI 或环境变量传入账号密码，不把 `TNProject01` 写死到仓库文件。
- `slider_solver.py` 只做图像求解，不直接依赖 Playwright。
- 主流程不调用 `tinno/output/img_gen.py`；如果后续要做模型实验，作为独立分支，不混入本次 PoC 主线。

**测试场景**

- 入口页未勾选隐私政策时会弹提示；PoC 必须先勾选后再跳转。
- UAC 登录页在 `domcontentloaded` 后 5 秒内能拿到 `#input-loginname`、`#input-password`、`#btn-signin`。
- 密码框点击后 `readonly` 被移除，能正常输入。
- 登录提交后能收到 `jigsaw` 响应，且返回键为 `bigImg`、`smallImg`、`yHeight`。
- 求解结果必须满足：
  - `target_x` 在图板宽度范围内
  - `drag_distance > 0`
  - `confidence` 高于设定阈值
- 拖动后成功判定为以下之一：
  - `Authentication` 弹窗消失
  - 页面不再停留在登录态
  - 出现后续跳转/授权行为
- 拖动失败时必须触发刷新重试，并产出对应调试文件。

**默认假设**

- 本次实现语言用 Python，浏览器驱动用当前环境已有的 Playwright。
- 本次目标是验证“接口/CV 路线能跑通”，不是把滑块能力抽成生产级 SDK。
- 纯 OpenCV 足够支撑第一版 PoC；不引入模型兜底。
- 若匹配分数长期不稳定，再单独规划 `img_gen.py` 或多模态实验分支，而不是回退主线设计。
