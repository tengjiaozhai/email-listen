"""
企微群机器人通知模块。
"""

from pathlib import Path

import requests


def send_text(webhook: str, send_number: str) -> None:
    """发送文本提醒消息到企微群机器人。"""
    payload = {
        "msgtype": "text",
        "text": {
            "content": (
                f"@所有人【发放单提醒】\n"
                f"本次发放单编号：{send_number}\n"
                "请相关人员前往 BPM 系统查阅核对，知悉办理～"
            ),
            "mentioned_list": ["@all"],
        },
    }
    resp = requests.post(webhook, json=payload, timeout=10)
    resp_json = resp.json()
    if resp_json.get("errcode", 0) != 0:
        raise RuntimeError(f"wecom text send failed: {resp_json}")


def send_file(webhook: str, file_path: Path) -> None:
    """上传文件并发送 file 消息到企微群机器人。"""
    # 构建 upload_media URL：将 /send?key=KEY 替换为 /upload_media?type=file&key=KEY
    if "?" in webhook:
        base, query = webhook.split("?", 1)
        # base 形如 https://qyapi.weixin.qq.com/cgi-bin/webhook/send
        upload_base = base.replace("/send", "/upload_media")
        upload_url = f"{upload_base}?type=file&{query}"
    else:
        upload_url = webhook.replace("/send", "/upload_media") + "?type=file"

    # Step 1: 上传文件
    with open(file_path, "rb") as f:
        upload_resp = requests.post(
            upload_url,
            files={"media": (file_path.name, f)},
            timeout=30,
        )
    upload_json = upload_resp.json()
    if upload_json.get("errcode", 0) != 0:
        raise RuntimeError(f"wecom file upload failed: {upload_json}")
    media_id = upload_json["media_id"]

    # Step 2: 发送 file 消息
    payload = {
        "msgtype": "file",
        "file": {"media_id": media_id},
    }
    send_resp = requests.post(webhook, json=payload, timeout=10)
    send_json = send_resp.json()
    if send_json.get("errcode", 0) != 0:
        raise RuntimeError(f"wecom file send failed: {send_json}")


def notify(webhook: str, send_number: str, extracted_files: list[Path]) -> dict:
    """组合通知函数：先发文本提醒，再逐个发送文件。"""
    result = {
        "text_sent": False,
        "files_sent": [],
        "error": None,
    }

    try:
        send_text(webhook, send_number)
        result["text_sent"] = True
    except Exception as e:
        result["error"] = str(e)
        return result

    for file_path in extracted_files:
        try:
            send_file(webhook, file_path)
            result["files_sent"].append(file_path.name)
        except Exception as e:
            result["error"] = str(e)
            return result

    return result
