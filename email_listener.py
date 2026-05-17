"""
邮件实时监听 demo
使用 IMAP IDLE 协议，邮件到达时服务器主动推送通知，无需轮询。
"""

import ssl
import time
import logging
import imaplib
import email
from email.header import decode_header
from datetime import datetime

import imapclient

# ── 配置 ──────────────────────────────────────────────────
IMAP_HOST = "imap.tinno.com"
IMAP_PORT = 993
USERNAME  = "mingjie.shen@tinno.com"
PASSWORD  = "Smj0409!@#"
MAILBOX   = "INBOX"

# IDLE 超时后重连间隔（Exchange 建议 IDLE 不超过 29 分钟）
IDLE_TIMEOUT   = 25 * 60   # 25 分钟
RECONNECT_WAIT = 10        # 断线后等待 N 秒再重连
# ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def make_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE   # 内网自签证书，跳过校验
    return ctx


def decode_str(s):
    """解码邮件头部字段（处理 =?UTF-8?...?= 编码）"""
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


def fetch_and_print(client, msg_ids):
    """拉取指定 UID 列表的邮件并打印摘要"""
    if not msg_ids:
        return
    log.info("拉取 %d 封新邮件: %s", len(msg_ids), msg_ids)
    raw_messages = client.fetch(msg_ids, ["RFC822"])
    for uid, data in raw_messages.items():
        raw = data[b"RFC822"]
        msg = email.message_from_bytes(raw)

        subject = decode_str(msg.get("Subject", "（无主题）"))
        sender  = decode_str(msg.get("From", ""))
        date    = msg.get("Date", "")

        print("\n" + "=" * 60)
        print(f"  UID    : {uid}")
        print(f"  时间   : {date}")
        print(f"  发件人 : {sender}")
        print(f"  主题   : {subject}")
        print("=" * 60)

        # 如需处理正文，在此扩展 ↓
        # body = get_body(msg)


def connect():
    """建立 IMAP 连接并选择收件箱，返回 (client, initial_uid_set)"""
    log.info("连接 %s:%s ...", IMAP_HOST, IMAP_PORT)
    client = imapclient.IMAPClient(
        IMAP_HOST, port=IMAP_PORT, ssl=True, ssl_context=make_ssl_context()
    )
    client.login(USERNAME, PASSWORD)
    log.info("登录成功")

    client.select_folder(MAILBOX)

    # 记录当前已有的 UID，避免把历史邮件当新邮件处理
    existing = set(client.search(["ALL"]))
    log.info("当前收件箱共 %d 封邮件，开始监听新邮件...", len(existing))
    return client, existing


def listen():
    """主循环：连接 → IDLE 等待 → 处理通知 → 循环"""
    client, known_uids = connect()

    while True:
        try:
            log.info("进入 IDLE 模式（超时 %d 分钟）", IDLE_TIMEOUT // 60)
            client.idle()
            responses = client.idle_check(timeout=IDLE_TIMEOUT)
            client.idle_done()

            if responses:
                log.info("收到服务器推送: %s", responses)
                # 重新搜索，找出新到的 UID
                current_uids = set(client.search(["ALL"]))
                new_uids = current_uids - known_uids
                if new_uids:
                    fetch_and_print(client, list(new_uids))
                    known_uids = current_uids
                else:
                    log.info("推送为状态变更（非新邮件），忽略")
            else:
                # IDLE 超时，重新进入（保持连接活跃）
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
            client, known_uids = connect()


if __name__ == "__main__":
    listen()
