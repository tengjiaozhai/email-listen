# 公司邮件服务器调研记录

**调研时间：** 2026-05-15

---

## 一、端口扫描结果

测试主机列表及关键端口（993 / 143 / 995 / 110 / 443）：

| 主机 | 993 | 143 | 995 | 110 | 443 | 备注 |
|------|-----|-----|-----|-----|-----|------|
| `imap.tinno.com` | OPEN | OPEN | OPEN | OPEN | OPEN | 解析到 172.16.159.102 |
| `mail.tinno.com` | OPEN | OPEN | OPEN | OPEN | OPEN | 同上，同一 IP |
| `autodiscover.tinno.com` | OPEN | OPEN | OPEN | OPEN | OPEN | 解析到 172.16.5.28（Exchange 自动发现服务）|
| `exchange.tinno.com` | CLOSED | CLOSED | CLOSED | CLOSED | CLOSED | DNS 无法解析 |
| `mx.tinno.com` | CLOSED | CLOSED | CLOSED | CLOSED | CLOSED | 不通 |

---

## 二、DNS 解析

```
imap.tinno.com        -> 172.16.159.102
mail.tinno.com        -> 172.16.159.102   （与 imap 同一台机器）
autodiscover.tinno.com -> 172.16.5.28
exchange.tinno.com    -> （无法解析）
```

---

## 三、服务器识别

通过 SSL 证书和 IMAP Banner 确认：

- **实际主机名（证书 CN）：** `mailbox04.tinno.com`
- **证书颁发机构：** `tinno-TNDC01-CA-2`（内网 CA）
- **证书有效期：** 2025-10-14 ~ 2030-10-13

### IMAP Banner

```
* OK The Microsoft Exchange IMAP4 service is ready.
```

### CAPABILITY 响应

```
* CAPABILITY IMAP4 IMAP4rev1 AUTH=PLAIN AUTH=NTLM AUTH=GSSAPI
  SASL-IR UIDPLUS MOVE ID UNSELECT CHILDREN IDLE NAMESPACE LITERAL+
```

---

## 四、结论

**邮件服务类型：Microsoft Exchange（IMAP4 接口）**

### 推荐监听配置

| 参数 | 值 |
|------|----|
| 服务器 | `imap.tinno.com` |
| 端口 | `993` |
| 加密 | SSL/TLS |
| 认证方式 | `AUTH=PLAIN`（用户名 + 密码）或 `AUTH=NTLM` |
| IDLE 推送 | 支持（服务器主动通知，无需轮询） |

### 关键特性

- **IDLE 支持**：可实现真正的实时推送监听，邮件到达时服务器主动通知，无需定时轮询。
- **AUTH=PLAIN**：在 SSL 保护下使用用户名/密码登录，实现最简单。
- **AUTH=NTLM / GSSAPI**：支持 Windows 域认证（Kerberos），适合域账号集成。

### 不可用主机

- `exchange.tinno.com`：所有端口关闭，DNS 无记录，不可用。
- `mx.tinno.com`：所有端口关闭，不可用。
- `autodiscover.tinno.com`：虽端口开放，但为 Exchange 自动发现服务（另一台机器），不用于 IMAP 连接。


你的程序                    Exchange 服务器
   |                              |
   |-- LOGIN ─────────────────>   |
   |-- SELECT INBOX ──────────>   |
   |-- IDLE ──────────────────>   |  ← 发完这条命令后"挂着"
   |                              |
   |           （有新邮件时）       |
   |<── * 5 EXISTS ────────────   |  ← 服务器主动推过来
   |                              |
   |-- DONE ──────────────────>   |  ← 结束 IDLE，去取邮件
   |-- FETCH 5 ───────────────>   |
   |<── 邮件内容 ───────────────   |
   |-- IDLE ──────────────────>   |  ← 重新进入等待



邮箱监听服务
  ↓
监听收件人: mingjie.shen@tinno.com
  ↓
写入 scm_download_ta sk 任务表
  ↓
Playwright Worker 拉取待处理任务
  ↓
登录客户 SCM 系统
打开链接：https://supply.zte.com.cn/sscm/UI/Web/Application/kxscm/kxsup_manager/Portal/index.aspx
点击登录 -> 输入账号:TNProject01 输入密码:TNProject01 -> 点击登录 -> 通过滑块验证码 -> 点击进入系统
  ↓
进入：供方管理 → 供方发放下拉框 -> 点击供方发放 -> 点击是 → 进入供方发放页面
  ↓
筛选/获取“未签收”发放单
  ↓
点击发放单编号
  ↓
下载“生产技术通知单”右侧的 下载1 / 下载2
  ↓
返回列表，继续下一个发放单
  ↓
全部下载成功后结束任务

## 2026-05-17 供方发放自动化补充

- 系统入口页点击 `进入系统` 后进入 `Index.aspx?TYPE=0`
- 顶部业务菜单 frame 名称：`news`
- 左侧功能树 frame 名称：`leftup`
- 主内容 frame 名称：`right`
- `供方发放` 菜单需要先展开 `#RightNavigationMenu_MenuSection4_SectionHeader`
- 引导页按钮：`#ibtnEnter`
- 列表页控件：`#ddlSignStatus`、`#btnQuery`、`#dtg_Doclist__ctl3_HyperLink1`
- 详情页下载按钮：`#dtg_AttachList__ctl3_Linkbutton1`、`#dtg_AttachList__ctl3_Linkbutton2`
- 页面文案提示若浏览器原生弹窗出现，应选择 `否`