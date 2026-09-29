# 校园 WebVPN（vpn.neuq.edu.cn）技术处理说明

东北大学秦皇岛分校的校外访问通常两种形态，本技能都支持。

## 1. 网页版 VPN 反代（深信服，常见）
- 登录入口：`https://vpn.neuq.edu.cn/`
- 登录后浏览器即处于"校内网"，可直接访问代理出来的各数据库（知网、万方、维普、Web of Science 镜像、SciFinder 等）。
- 代理地址形态：`https://vpn.neuq.edu.cn/https/<base64(目标域名)>/...`
  - 例如知网：`/https/77726476706e69737468656265737421e7e056d2243e635930068cb8/`（即 `kns.cnki.net` 的代理编码）。
  - `/https/` 后那串是目标域名的代理编码；`vpn.neuq.edu.cn` 上的会话 cookie 即机构通行证。
- **关键**：机构权限仅在代理域内有效。脚本默认直连公网 `kns.cnki.net` 必被"安全验证"挡（无头常态），必须走代理域。

## 2. 资源启动器反自动化（硬墙，决定混合接力模式）
- 门户「数字资源」里每个库入口 `href="javascript:void(0)"`，靠 JS 启动器在服务端**按次签发资源会话**，
  返回带 `wrdrecordvisit` 令牌的代理 URL；直链无此会话 → 一律踢回 `vpn.neuq.edu.cn/login`。
- `wrdrecordvisit` 每次点击刷新，不可复用。
- 启动器检测 `window.chrome.runtime` 是否存在来判机器人：
  - Playwright 接管的 Edge，其 `window.chrome` 是**只读冻结对象**，只暴露 `loadTimes/csi/app`，
    **刻意无 `runtime` 且不可重定义**。
  - 注入 stealth（`Object.defineProperty(window,'chrome',{...runtime...})`）被 `non-configurable` 挡掉，无法伪造 `runtime`。
  - `--disable-blink-features=AutomationControlled` 能藏 `navigator.webdriver`（已验证 false），但挡不住 `runtime` 检测。
  - 本机未装 Chrome（仅 Edge），`channel="chrome"` 报找不到；真 Chrome 自带 `runtime` 可破此局，但环境不具备。
- **结论**：纯 agent 浏览器自动点「知网/万方/WOS」被堵死（环境限制，非配置可解）。必须走混合接力。

## 3. 混合接力（可行方案）
- 用户在自己的真 Edge（有 `runtime` + 已登录 VPN）点「数字资源」里的目标库 → 生成新鲜令牌代理 URL。
- 用户把该 URL 贴给智能体；智能体浏览器复用 VPN 会话 cookie 加载并驱动检索/抽取。
- 已端到端验证：WOS（`/wos/` 路径，最终进 smart-search，redirected_to_login=false）、万方、
  知网（中文期刊）均可经此加载真实资源页。

## 4. 会话时效（重要）
- WebVPN 的 VPN Web 会话 cookie **几分钟就过期**。资源令牌不足以独立放行——agent 必须持"活的"VPN 会话 cookie。
- 故每批检索前需用户在 agent 窗口重新登一次 VPN（cookie 落 profile 后关窗不影响已存 cookie，但会话本身会过期）。
- 门户根路径在会话失效时只剩登录页导航，抽不到资源目录；需有效会话才能抽「数字资源」全量清单。

## 5. 排错
- 登录窗口弹不出 / 卡住：确认本机有 Chrome 或 Edge；或 `PATENT_BROWSER_CHANNEL=chrome` 指定。
- 加载资源被踢回 login：VPN 会话 cookie 已过期 → 用户重登 VPN 并贴新鲜令牌 URL。
- 检索框找不到 / 抽取为空：不同库 DOM 不同；用 `metalib_query.py` 不带 `--query` 仅 dump 页面 HTML，
  由智能体据 HTML 做选择器发现后二次驱动（见 prompts/query.md）。
- cookies 过期：知网会话通常几小时~几天失效，失效后重跑 `campus_login.py` 重新登录即可。
