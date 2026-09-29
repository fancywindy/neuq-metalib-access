#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建立并持久化东大秦皇岛校园库的登录态会话（通用版，覆盖全部 MetaLib 库）。

流程：
  1. 启动有头浏览器（持久化 profile，cookies 落盘到 sessions/profile_<name>/）
  2. 开校园VPN登录页 vpn.neuq.edu.cn，等你登录
  3. 轮询哨兵文件 sessions/<name>/.ready（智能体在你说"登录好了"时创建）
     检测到即保存 cookies 备份、打印 SESSION_READY、关闭浏览器

注意：本脚本只建会话。真正点开某个库（知网/万方/WOS...）由你在自己的真 Edge 里完成，
并把新鲜代理 URL 贴给智能体（混合接力）。原因见 SKILL.md / references/vpn.md。

用法：
  python campus_login.py --session-name neuq
  python campus_login.py --session-name neuq --no-vpn        # 已用 EasyConnect 等连校园网时
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"
DEFAULT_VPN = "https://vpn.neuq.edu.cn/"

# 反自动化检测：门户启动器靠 window.chrome.runtime 区分真人与 Playwright；
# 缺失时禁用「数字资源」的 JS 启动器（agent 点资源无反应）。此处 best-effort 补齐，
# 但实测无法伪造 runtime（只读冻结、non-configurable），仅作兼容、不影响混合接力主流程。
STEALTH_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"
STEALTH_JS = """() => {
  try { Object.defineProperty(navigator, 'webdriver', { get: () => false, configurable: true }); } catch(e){}
  const fc = { runtime:{ id:'', getManifest:()=>({}), getURL:()=>'', connect:()=>{}, sendMessage:()=>{}, onMessage:{addListener:()=>{}, removeListener:()=>{}} }, csi:function(){}, loadTimes:function(){}, app:{}, webstore:{} };
  try { Object.defineProperty(window, 'chrome', { get: () => fc, configurable: true }); } catch(e){ try { window.chrome = fc; } catch(_){} }
}"""


def detect_channel() -> str | None:
    raw = os.environ.get("PATENT_BROWSER_CHANNEL", "").strip().lower()
    if raw in ("chrome", "msedge"):
        return raw
    if raw in ("chromium", "bundled", "playwright"):
        return None
    return None  # 自动探测：chrome -> msedge -> chromium


def main() -> int:
    ap = argparse.ArgumentParser(description="建立并持久化东大秦皇岛校园库登录态（通用）")
    ap.add_argument("--session-name", default="default", help="会话名，区分多套登录态")
    ap.add_argument("--no-vpn", action="store_true", help="跳过校园VPN登录（已用客户端连校园网）")
    ap.add_argument("--vpn-url", default=DEFAULT_VPN)
    ap.add_argument("--channel", default="", help="chrome|msedge|chromium|（空=自动）")
    ap.add_argument("--timeout", type=int, default=3600, help="等待登录哨兵的最长秒数")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    profile_dir = SESSIONS_DIR / f"profile_{args.session_name}"
    session_file = SESSIONS_DIR / f"{args.session_name}.json"
    sentinel = SESSIONS_DIR / f"{args.session_name}.ready"

    channel = args.channel or detect_channel() or None
    print(f"🔓 正在打开登录窗口（profile={profile_dir.name}, channel={channel or 'auto'}）", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            channel=channel,
            user_agent=STEALTH_UA,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--start-maximized"],
        )
        browser.add_init_script(STEALTH_JS)
        try:
            if not args.no_vpn:
                page = browser.new_page()
                page.goto(args.vpn_url, wait_until="domcontentloaded")
                print(f"   ① 请在浏览器中登录校园VPN：{args.vpn_url}", flush=True)
            print("   ② VPN 登录后，在门户里找到「数字资源」板块，准备点开你要查的库", flush=True)
            print("      （注意：agent 浏览器无法自动点资源入口——请在你自己的真 Edge 里点开目标库，", flush=True)
            print("       把地址栏里带 wrdrecordvisit 的代理 URL 贴给智能体，由它复用本会话 cookie 检索）", flush=True)
            print("   ③ 确认 VPN 已登录、能正常进资源后，回到对话告诉我「登录好了」，", flush=True)
            print("      我会标记就绪并关闭窗口。", flush=True)

            deadline = time.time() + args.timeout
            ready = False
            while time.time() < deadline:
                if sentinel.exists():
                    ready = True
                    break
                time.sleep(3)
            if not ready:
                print("LOGIN_TIMEOUT: 等待哨兵超时，已关闭窗口（profile 可能含部分 cookies）", file=sys.stderr, flush=True)
                return 1

            cookies = browser.cookies()
            session_file.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
            print(f"SESSION_READY: {session_file} (cookies={len(cookies)})", file=sys.stderr, flush=True)
            print(f"✅ 登录态已保存。之后检索用：metalib_query.py --start-url \"<你贴的URL>\" --session-name {args.session_name}", flush=True)
            return 0
        finally:
            try:
                sentinel.unlink(missing_ok=True)
            except Exception:
                pass
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
