#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用验证：用已登录 profile 加载用户给的新鲜代理URL，判断 agent 侧能否真正进入资源页
（而非被踢回 login）。用法：verify_resource.py "<url>" [session-name]
"""
import sys
import json
import time
from pathlib import Path

SESSIONS = Path(r"C:/Users/wumin/.workbuddy/skills/neuq-metalib-access/sessions")
STEALTH_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: verify_resource.py \"<url>\" [session-name]", file=sys.stderr)
        return 2
    url = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else "neuq"
    profile = SESSIONS / f"profile_{name}"
    if not profile.exists():
        print(f"ERROR: 未找到 profile {profile}", file=sys.stderr); return 1
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch_persistent_context(
            user_data_dir=str(profile), headless=True, channel="msedge",
            user_agent=STEALTH_UA,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-popup-blocking"],
        )
        try:
            pg = b.new_page()
            pg.goto(url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(7)
            title = pg.title()
            final = pg.url
            body = pg.evaluate("()=>document.body?document.body.innerText.replace(/\\s+/g,' ').slice(0,400):''")
            redirected = ("login" in final.lower()) or ("login" in title.lower())
            print(json.dumps({
                "final_url": final,
                "title": title,
                "redirected_to_login": redirected,
                "body_snippet": body,
            }, ensure_ascii=False, indent=2))
            return 0
        finally:
            b.close()


if __name__ == "__main__":
    raise SystemExit(main())
