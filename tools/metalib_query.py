#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用 MetaLib 库检索（混合接力）。

加载用户贴来的新鲜代理 URL（带 wrdrecordvisit 令牌），可选填关键词检索；
dump 页面 HTML 供选择器发现，尽力抽取题名/作者/来源/链接。

依赖：campus_login.py 已建立 sessions/profile_<name>/ 持久化登录态（VPN cookie 落盘）。
用法：
  python metalib_query.py --start-url "<用户贴来的新鲜代理URL>" --query "关键词" \
      --session-name neuq --library wos --channel msedge
  python metalib_query.py --start-url "<URL>" --session-name neuq --library cnki --no-query   # 仅加载并 dump
输出：
  sessions/<library>_result.json   {library, query, count, results:[{title,authors,source,date,link}]}
  sessions/<library>_page.html     dump 的页面 HTML（供选择器发现/二次精准抽取）
说明：
  - 各库 DOM 不同，自动检索框探测覆盖常见模式；若未命中，工具仅加载并 dump 页面，
    由智能体据 HTML 做选择器发现后二次驱动（见 prompts/query.md）。
  - 知网特例：首页 textarea#txt_SearchText + div.search-btn；结果页 #txt_search/#gridTable。
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from datetime import datetime

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"

STEALTH_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"
STEALTH_JS = """() => {
  try { Object.defineProperty(navigator, 'webdriver', { get: () => false, configurable: true }); } catch(e){}
  const fc = { runtime:{ id:'', getManifest:()=>({}), getURL:()=>'', connect:()=>{}, sendMessage:()=>{}, onMessage:{addListener:()=>{}, removeListener:()=>{}} }, csi:function(){}, loadTimes:function(){}, app:{}, webstore:{} };
  try { Object.defineProperty(window, 'chrome', { get: () => fc, configurable: true }); } catch(e){ try { window.chrome = fc; } catch(_){} }
}"""

# 自动填词：扫描常见检索框选择器，命中可见框则填入并返回选择器名
AUTO_FILL_JS = """(query) => {
  const cands = [
    'textarea#txt_SearchText', 'input#txt_SearchText',
    'input#txt_search', 'input#searchInput', 'input#keyword', 'input#kw',
    'input[type=search]',
    'input[name*=search i]', 'input[name*=keyword i]', 'input[name*=kw i]', 'input[name*=q i]',
    'input[placeholder*=检索 i]', 'input[placeholder*=搜索 i]', 'input[placeholder*=关键词 i]',
    'input.search-input', 'input.query', 'input.kw', 'input.search'
  ];
  function setVal(el, v){
    try {
      const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(el, v);
    } catch(e){ el.value = v; }
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }
  for (const sel of cands) {
    const el = document.querySelector(sel);
    if (el && el.offsetParent !== null && el.type !== 'hidden') {
      el.focus(); setVal(el, query);
      return {filled: sel, tag: el.tagName};
    }
  }
  const inp = [...document.querySelectorAll('input,textarea')].find(i =>
    i.type !== 'hidden' && i.offsetParent !== null && (i.offsetWidth||0) > 50 && (i.offsetHeight||0) > 10);
  if (inp) { inp.focus(); setVal(inp, query); return {filled: 'fallback:'+(inp.id||inp.name||inp.className), tag: inp.tagName}; }
  return {filled: null};
}"""

# 通用抽取：抓结果容器内 a 元素（题名）+ 尽力附作者/来源/年；按 link 或 title 去重
EXTRACT_JS = """
() => {
  const out = [];
  const containers = [
    document.querySelector('#gridTable'), document.querySelector('#briefBox'),
    document.querySelector('#results'), document.querySelector('.result-list'),
    document.querySelector('table.list'), document.querySelector('.doc-list'),
    document.body
  ].filter(Boolean);
  const seen = new Set();
  for (const root of containers) {
    const anchors = root.querySelectorAll('a');
    for (const a of anchors) {
      const t = (a.innerText || '').replace(/\\s+/g,' ').trim();
      if (t.length < 6 || t.length > 220) continue;
      let link = '';
      try { link = new URL(a.href, location.href).href; } catch(e){ link = a.href || ''; }
      if (!link || link.includes('javascript:')) continue;
      const key = link || t;
      if (seen.has(key)) continue;
      seen.add(key);
      // 尽力找同行/父容器的作者、来源、日期
      let authors='', source='', date='';
      const row = a.closest('tr, li, .doc-item, .result-item, div[class*=item]');
      if (row) {
        const txt = row.innerText.replace(/\\s+/g,' ').trim();
        const m = txt.match(/(\\d{4}[-/.]?\\d{0,2}[-/.]?\\d{0,2})/);
        date = m ? m[1] : '';
        const parts = txt.split(/[\\s　]+/).filter(Boolean);
        if (parts.length > 1) { authors = parts.slice(1,4).join(' '); source = parts[parts.length-1]||''; }
      }
      out.push({title: t, link: link, authors: authors, source: source, date: date});
    }
  }
  return out;
}
"""

def find_submit_and_submit(page, filled):
    """填词后提交：优先点文字含检索/搜索/Search 的按钮，否则对框按 Enter。"""
    if not filled:
        return False
    try:
        btn = page.query_selector("button:has-text('检索'), button:has-text('搜索'), "
                                  "button:has-text('Search'), button:has-text('查询'), "
                                  "input[type=submit], a.search-btn, div.search-btn")
        if btn:
            btn.click(timeout=5000)
            return True
    except Exception:
        pass
    try:
        page.keyboard.press("Enter")
        return True
    except Exception:
        return False

def main() -> int:
    ap = argparse.ArgumentParser(description="通用 MetaLib 库检索（混合接力）")
    ap.add_argument("--start-url", required=True, help="用户贴来的新鲜代理 URL（带 wrdrecordvisit）")
    ap.add_argument("--query", default="")
    ap.add_argument("--session-name", default="neuq")
    ap.add_argument("--library", default="lib", help="库简称，用于命名输出文件")
    ap.add_argument("--channel", default="msedge")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--no-query", action="store_true", help="仅加载并 dump 页面，不检索")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    profile_dir = SESSIONS_DIR / f"profile_{args.session_name}"
    if not profile_dir.exists():
        print(f"ERROR: 未找到 profile {profile_dir}，请先跑 campus_login.py", file=sys.stderr); return 1

    stamp = datetime.now().strftime("%Y%m%d")
    html_path = SESSIONS_DIR / f"{args.library}_{stamp}_page.html"
    out_path = SESSIONS_DIR / f"{args.library}_{stamp}_result.json"

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir), headless=not args.headed,
            channel=args.channel, user_agent=STEALTH_UA,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-popup-blocking"])
        browser.add_init_script(STEALTH_JS)
        try:
            page = browser.new_page()
            page.goto(args.start_url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            time.sleep(5)
            # dump 页面（供选择器发现）
            html_path.write_text(page.content(), encoding="utf-8", errors="ignore")
            title = page.title()
            final = page.url
            redirected = ("login" in final.lower()) or ("login" in title.lower())
            print(json.dumps({"final_url": final, "title": title, "redirected_to_login": redirected,
                              "dumped_html": str(html_path)}, ensure_ascii=False), file=sys.stderr)

            if args.no_query or not args.query:
                print("NO_QUERY: 已加载并 dump 页面，未检索。请据 HTML 做选择器发现。", file=sys.stderr)
                payload = {"library": args.library, "query": args.query or None,
                           "count": 0, "redirected_to_login": redirected,
                           "results": [], "note": "loaded+dumped, no query"}
                out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                return 0

            if redirected:
                print("REDIRECTED: 被踢回 login，VPN 会话已过期，请重登 VPN 并贴新鲜 URL。", file=sys.stderr)
                return 3

            res = page.evaluate(AUTO_FILL_JS, args.query)
            filled = res.get("filled") if isinstance(res, dict) else None
            print(f"FILL: {filled}", file=sys.stderr)
            if not filled:
                print("FILL_FAIL: 未探测到检索框，已 dump 页面供选择器发现。", file=sys.stderr)
                payload = {"library": args.library, "query": args.query, "count": 0,
                           "redirected_to_login": redirected, "results": [], "note": "no search box detected"}
                out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                return 0
            find_submit_and_submit(page, filled)
            # 等待结果
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            time.sleep(5)
            # 刷新 dump
            html_path.write_text(page.content(), encoding="utf-8", errors="ignore")
            rows = page.evaluate(EXTRACT_JS)
            rows = rows[:args.max]
            payload = {"library": args.library, "query": args.query, "count": len(rows),
                       "redirected_to_login": redirected, "results": rows}
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"SAVED: {out_path} ({len(rows)} 条)", file=sys.stderr)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        finally:
            browser.close()

if __name__ == "__main__":
    raise SystemExit(main())
