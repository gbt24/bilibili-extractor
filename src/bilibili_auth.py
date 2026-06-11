"""Bilibili login — QR code scan + credential persistence.

Saves credentials to ~/.bilibili_cred.json so you only scan once.
Supports auto-refresh of expired tokens.
"""

import asyncio
import json
import os
from pathlib import Path

from bilibili_api import Credential, login_v2

CRED_FILE = Path.home() / ".bilibili_cred.json"


async def _qrcode_login() -> Credential:
    """Display QR code in terminal, wait for scan, return credential."""
    login_obj = login_v2.QrCodeLogin()
    await login_obj.generate_qrcode()
    print("\n请用 B站 App 扫描下方二维码登录：\n")
    print(login_obj.get_qrcode_terminal())

    while True:
        state = await login_obj.check_state()
        if state == login_v2.QrCodeLoginState.DONE:
            cred = login_obj.get_credential()
            print("\n登录成功！")
            return cred
        elif state == login_v2.QrCodeLoginState.EXPIRED:
            raise RuntimeError("二维码已过期，请重新运行")
        elif state == login_v2.QrCodeLoginState.SCAN:
            print("已扫码，请在手机上确认...")
        else:
            print("等待扫码...")
        await asyncio.sleep(2)


async def _check_and_refresh(cred: Credential) -> Credential:
    """Check if credential is still valid; try to refresh if expired."""
    try:
        if await cred.check_valid():
            return cred
    except Exception:
        pass

    try:
        await cred.refresh()
        return cred
    except Exception:
        pass

    return cred


def _save_credential(cred: Credential) -> None:
    data = {
        "sessdata": cred.sessdata,
        "bili_jct": cred.bili_jct,
        "dedeuserid": cred.dedeuserid,
        "ac_time_value": getattr(cred, "ac_time_value", ""),
    }
    CRED_FILE.write_text(json.dumps(data))


def _load_credential() -> Credential | None:
    if not CRED_FILE.is_file():
        return None
    try:
        data = json.loads(CRED_FILE.read_text())
        return Credential(
            sessdata=data.get("sessdata", ""),
            bili_jct=data.get("bili_jct", ""),
            dedeuserid=data.get("dedeuserid", ""),
            ac_time_value=data.get("ac_time_value", ""),
        )
    except Exception:
        return None


async def get_credential() -> Credential:
    """Get a valid Bilibili credential. QR-login on first run; auto-refresh thereafter."""
    cred = _load_credential()

    if cred is not None:
        cred = await _check_and_refresh(cred)
        try:
            if await cred.check_valid():
                print("B站登录态有效")
                return cred
        except Exception:
            pass
        print("登录态已过期，需要重新扫码")

    cred = await _qrcode_login()
    _save_credential(cred)
    return cred
