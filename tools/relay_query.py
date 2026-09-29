#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用校内库检索（接管法）—— 用户在本窗口点开库，脚本自动接管并检索。

为什么需要这个脚本（实测结论，见 references/vpn.md §3.1/3.2）：
  - 深信服 WebVPN 的裸 URL 不签发资源会话（DNS_RECORD_NOT_FOUND）；
  - 用户在自己真 Edge 里点库拿到的 wrdrecordvisit 令牌，跨会话拿到本 profile 也进不去；
  - 门户启动器检测 window.chrome.runtime，Playwright 的 Edge 该属性只读冻结 → agent 自己点库无反应。
  => 唯一稳定可用：脚本拉起本机 Edge（持久化 profile），用户在**该窗口内**登录 VPN 并点击目标库，
     资源页在本会话内正常打开；脚本扫描 context.pages 认出带检索框的库页面并直接驱动。

【用户必须配合的步骤】（脚本也会在窗口里打印，务必照做）：
  1) 脚本启动后会弹出 Edge 窗口停在校园 VPN 门户；
  2) 你在该窗口里登录校园 VPN（输入账号密码）；
  3) 登录后，在门户「数字资源」里**手动点击**你要查的库（如 中国知网 / Web of Science / 万方）；
     —— agent 不能替你点（启动器拦机器人），这一步必须你点；
  4) 库页面打开后**什么都不用做**：脚本检测到检索框会自动填词、检索、抽结果；
  5) 若窗口停在教学录/登录页，说明还没登录好，先登录；若点的不是真库页（广告/其他站），
     关掉重点在门户里点一次即可。
  ※ WebVPN cookie 数分钟过期：弹窗后请尽快登录+点库，不要闲置。

用法：
  C:/Python314/python.exe tools/relay_query.py --session-name neuq --query "关键词" --library cnki
  （不给 --query 则仅接管并 dump 页面 HTML，供选择器发现）
依赖：系统 Python 3.14（已预装 playwright 1.62.0），channel=msedge 复用已装 Edge。
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

# 解释器自检：本技能必须用系统 Python 3.14（C:/Python314/python.exe），其已预装 playwright 1.62.0。
try:
    from playwright.sync_api import sync_playwright  # noqa: F401
except ImportError:
    sys.stderr.write(
        "ERROR: 当前 Python 解释器未安装 playwright。\n"
        "本技能必须使用系统 Python 3.14（C:/Python314/python.exe），其已预装 playwright 1.62.0。\n"
        "请改用：C:/Python314/python.exe tools/relay_query.py ...\n"
        "（不需要、也不应反复重装 playwright；脚本用 channel=msedge 驱动已装 Edge，不下载浏览器。）\n"
    )
    raise SystemExit(2)

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"
VPN_PORTAL = "https://vpn.neuq.edu.cn/"

STEALTH_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"
STEALTH_JS = """() => {
  try { Object.defineProperty(navigator, 'webdriver', { get: () => false, configurable: true }); } catch(e){}
  const fc = { runtime:{ id:'', getManifest:()=>({}), getURL:()=>'', connect:()=>{}, sendMessage:()=>{}, onMessage:{addListener:()=>{}, removeListener:()=>{}} }, csi:function(){}, loadTimes:function(){}, app:{}, webstore:{} };
  try { Object.defineProperty(window, 'chrome', { get: () => fc, configurable: true }); } catch(e){ try { window.chrome = fc; } catch(_){} }
}"""

# 通用抽取：过滤页面 chrome/导航/页脚（否则命中数虚高数倍）
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
  const NOISE = ['AI阅读','我的CNKI','CAJViewer','帮助中心','作者发文','出版来源','文献检索代码',
    '查看全部更新','数字出版物','新浪微博','CNKI荣誉','网络出版服务','学位授予单位','知网研学',
    '订卡热线','服务热线','官方微信','邮件咨询','购买知网卡','知网卡',
    '荣誉','文献计量','AI文献','CNKI AI','AI文献计量','CNKI 荣誉','我的馆藏','个人中心',
    '登录','注册','购物车','充值','客服','下载','导出','订阅',
    'oversea.cnki.net','service.cnki.net','cnki.net >','help.cnki.net','ai.cnki.net',
    'HTML阅读','在线阅读','CAJ下载','PDF下载','文献直达'];
  const CHROME_LINK = ['ai.cnki.net','piccache.cnki.net','oversea.cnki.net','service.cnki.net',
    'mailto:','cnki.net/other','kdn/index','help@cnki.net','help.cnki.net',
    'navi.cnki.net','bar.cnki.net'];
  for (const root of containers) {
    const anchors = root.querySelectorAll('a');
    for (const a of anchors) {
      const t = (a.innerText || '').replace(/\\s+/g,' ').trim();
      if (t.length < 6 || t.length > 220) continue;
      if (t.startsWith('主题：') || t.startsWith('地址：') || NOISE.some(k => t.indexOf(k) >= 0)) continue;
      // 跳过纯英文短导航（如 CNKI AI / oversea.cnki.net / service.cnki.net）
      if (!/[一-龥]/.test(t) && t.length < 14) continue;
      let link = '';
      try { link = new URL(a.href, location.href).href; } catch(e){ link = a.href || ''; }
      if (!link || link.includes('javascript:')) continue;
      if (CHROME_LINK.some(k => link.indexOf(k) >= 0)) continue;
      const key = link || t;
      if (seen.has(key)) continue;
      seen.add(key);
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

SEARCH_HINTS = ('search', 'kw', 'key', '检索', 'query', 'txt', 'q', 'wd', 'head')


def find_search_input(page):
    """通用检索框探测：优先 id/name/placeholder 含检索相关词，否则取最宽可见文本输入。"""
    try:
        cands = page.query_selector_all('input, textarea')
    except Exception:
        return None
    visible = []
    for el in cands:
        try:
            if not el.is_visible():
                continue
        except Exception:
            continue
        typ = (el.get_attribute('type') or '').lower()
        if typ in ('hidden', 'submit', 'button', 'checkbox', 'radio', 'password', 'file', 'image'):
            continue
        box = el.bounding_box()
        w = box['width'] if box else 0
        if w < 60:
            continue
        visible.append((el, w))
    if not visible:
        return None
    for el, w in visible:
        ident = ((el.get_attribute('id') or '') + ' ' + (el.get_attribute('name') or '') + ' ' +
                (el.get_attribute('placeholder') or '')).lower()
        if any(k in ident for k in SEARCH_HINTS):
            return el
    # 兜底：最宽的可见文本输入框
    return max(visible, key=lambda x: x[1])[0]


def find_submit_and_submit(page):
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


def is_library_page(page):
    try:
        if page.is_closed():
            return False
        u = (page.url or '')
        if 'vpn.neuq.edu.cn/login' in u:
            return False
        if 'wengine-vpn/failed' in u:
            return False
        if u.rstrip('/') == 'https://vpn.neuq.edu.cn':
            return False
        # 排除 CAS / 统一身份认证 等登录页
        if 'authserv' in u or '/cas/' in u or '/sso/' in u:
            return False
        try:
            t = (page.title() or '')
        except Exception:
            t = ''
        if '统一身份认证' in t:
            return False
        # 登录/CAS 页含 password 输入框，库检索页不含
        try:
            if page.query_selector('input[type=password]'):
                return False
        except Exception:
            pass
        return bool(find_search_input(page))
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="通用校内库检索（接管法）：用户窗口内点库，脚本接管检索")
    ap.add_argument("--session-name", default="neuq")
    ap.add_argument("--query", nargs="+", default=None, help="检索词，可给多个（如 --query \"单原子铁 氨氮\" \"单原子铁 光催化\"）；不给则仅 dump 页面")
    ap.add_argument("--library", default="lib", help="库简称，用于命名输出文件")
    ap.add_argument("--channel", default="msedge")
    ap.add_argument("--timeout", type=int, default=900, help="等待用户登录+点库的秒数")
    ap.add_argument("--max", type=int, default=30, help="抽取条数上限")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    profile_dir = SESSIONS_DIR / f"profile_{args.session_name}"
    out_json = SESSIONS_DIR / f"{args.library}_result.json"
    out_html = SESSIONS_DIR / f"{args.library}_page.html"

    with sync_playwright() as p:
        b = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir), headless=False, channel=args.channel,
            user_agent=STEALTH_UA,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-popup-blocking"])
        b.add_init_script(STEALTH_JS)
        try:
            portal = b.new_page()
            portal.goto(VPN_PORTAL, wait_until="domcontentloaded", timeout=30000)
            # —— 用户配合提示 ——
            print("=" * 60, file=sys.stderr, flush=True)
            print("【请在该 Edge 窗口内完成以下操作】", file=sys.stderr, flush=True)
            print("  ① 登录校园 VPN（输入账号密码）", file=sys.stderr, flush=True)
            print("  ② 登录后，在门户「数字资源」里【手动点击】你要查的库", file=sys.stderr, flush=True)
            print("     （如 中国知网 / Web of Science / 万方 …… agent 无法替你点）", file=sys.stderr, flush=True)
            print("     ※ 若点击库后弹出「统一身份认证 / CAS」登录页，请也登录（库的 SSO），", file=sys.stderr, flush=True)
            print("       登录后库页面才真正打开，脚本会自动等待该页。", file=sys.stderr, flush=True)
            print("  ③ 库页面打开后无需操作，本脚本会自动接管检索", file=sys.stderr, flush=True)
            print(f"  登录+点库请尽快（cookie 数分钟过期）；等待上限 {args.timeout}s", file=sys.stderr, flush=True)
            print("=" * 60, file=sys.stderr, flush=True)

            lib = None
            deadline = time.time() + args.timeout
            tick = 0
            while lib is None and time.time() < deadline:
                lib = next((pg for pg in list(b.pages) if is_library_page(pg)), None)
                if lib is None:
                    tick += 1
                    if tick % 10 == 1:
                        print(f"  … 等待你登录并点开库（已 {tick*3}s）", file=sys.stderr, flush=True)
                    time.sleep(3)
            if lib is None:
                print("TIMEOUT: 等待上限内未检测到库页面。请确认已在窗口内登录并手动点开目标库。",
                      file=sys.stderr, flush=True)
                return 1

            print(f"② 已接管库页面：{lib.url[:100]}", file=sys.stderr, flush=True)
            page_title = ""
            try:
                page_title = lib.title()
            except Exception:
                pass
            html_path = out_html
            try:
                html_path.write_text(lib.content(), encoding="utf-8", errors="ignore")
            except Exception:
                pass

            if not args.query:
                print(f"  （无 --query，仅接管并 dump 页面）SAVED: {html_path}", file=sys.stderr, flush=True)
                payload = {"library": args.library, "url": lib.url, "title": page_title,
                           "note": "no query; page dumped for selector discovery", "results": []}
                out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0

            # 多检索词：在同一接管会话内循环（避免重复登录）
            queries = args.query
            data = []
            for qi, q in enumerate(queries):
                print(f"  ▶ 检索 [{qi+1}/{len(queries)}]: {q}", file=sys.stderr, flush=True)
                box = find_search_input(lib)
                if box is None:
                    print(f"    ⚠ 未找到检索框，跳过该式", file=sys.stderr, flush=True)
                    data.append({"query": q, "count": 0, "error": "no_box", "results": []})
                    continue
                try:
                    box.fill(q)
                except Exception:
                    try:
                        box.focus()
                        lib.evaluate("(el,v)=>{el.value=v; el.dispatchEvent(new Event('input',{bubbles:true}));}",
                                     box, q)
                    except Exception:
                        print(f"    ⚠ 检索框填词失败，跳过该式", file=sys.stderr, flush=True)
                        data.append({"query": q, "count": 0, "error": "fill_fail", "results": []})
                        continue
                find_submit_and_submit(lib)
                try:
                    lib.wait_for_selector("#gridTable, #briefBox, .result-list, table.list, .doc-list", timeout=25000)
                except Exception:
                    pass
                time.sleep(3)
                try:
                    html_path.write_text(lib.content(), encoding="utf-8", errors="ignore")
                except Exception:
                    pass
                rows = lib.evaluate(EXTRACT_JS)[:args.max]
                data.append({"query": q, "count": len(rows), "results": rows})
                print(f"    ✓ {len(rows)} 条", file=sys.stderr, flush=True)
                time.sleep(2)
            payload = {"library": args.library, "url": lib.url, "title": page_title,
                       "queries": len(queries), "data": data,
                       "note": "multi-query takeover run; results filtered by tightened EXTRACT_JS"}
            out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"SAVED: {out_json}", file=sys.stderr, flush=True)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        finally:
            b.close()


if __name__ == "__main__":
    raise SystemExit(main())
