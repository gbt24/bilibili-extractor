#!/usr/bin/env python3
"""Bilibili QR code login. Only needed for paid/private courses."""

import asyncio
from src.bilibili_auth import get_credential

async def main():
    print("B站扫码登录\n")
    cred = await get_credential()
    print(f"\n已保存登录态，DedeUserID: {cred.dedeuserid}")

asyncio.run(main())
