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
from email.utils import getaddresses
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


def should_trigger(to_field: str, config: AppConfig) -> bool:
    """判断邮件收件人是否匹配配置的触发列表。

    trigger_recipients 为空时，所有邮件都触发（向后兼容）。
    否则检查 To 字段是否包含列表中的任意一个地址。
    """
    if not config.email.trigger_recipients:
        return True
    to_addresses = {
        addr.strip().lower()
        for _, addr in getaddresses([to_field or ""])
        if addr and addr.strip()
    }
    trigger_addresses = {
        addr.strip().lower()
        for addr in config.email.trigger_recipients
        if addr and addr.strip()
    }
    return bool(to_addresses & trigger_addresses)


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
    config: AppConfig,
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
                    fetch_and_process(client, list(new_uids), on_new_email, config)
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
