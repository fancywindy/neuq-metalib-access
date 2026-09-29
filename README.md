# neuq-metalib-access

东北大学秦皇岛分校校园 WebVPN **混合接力**检索 skill。复用用户真实登录态，检索校内 **171 个 MetaLib 数据库**（知网 CNKI、万方、维普、Web of Science、Scopus、ScienceDirect、SpringerLink、ACS、IEEE、RSC、Wiley、CAS SciFinder-n、Derwent、中外专利、ProQuest 博硕、CSSCI、NSTL 等）。

## 为什么必须"混合接力"

校园 WebVPN（深信服反代 `vpn.neuq.edu.cn`）的「数字资源」启动器检测 `window.chrome.runtime` 来区分真人与 Playwright；Playwright 接管的 Edge 该属性是**只读冻结对象**、刻意无 `runtime` 且不可重定义，注入 stealth 被 `non-configurable` 挡掉，故 **agent 浏览器无法自动点开资源入口**（点击无反应）。可行方案是混合接力：

1. 用户在自己的真 Edge（有 `runtime` + 已登录 VPN）里点开目标库，生成带 `wrdrecordvisit` 令牌的代理 URL；
2. 把该 URL 贴给智能体，智能体用同一套持久化浏览器 profile 复用 VPN 会话 cookie 加载并检索/抽取。

> `wrdrecordvisit` 每次点击刷新、**不可复用**；VPN 会话 cookie **数分钟过期**，每批检索前需用户重登 VPN 并贴新鲜 URL。

## 触发条件

用户提及需检索某具体库名（知网 / 万方 / WOS / Scopus / SciFinder / 中外专利 / …）并要检索 / 下载 / 查新时。

## 结构

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 完整说明与执行流程 |
| `tools/campus_login.py` | 建立持久化登录态（有头窗口，用户手动登录） |
| `tools/metalib_query.py` | 通用检索：自动探测检索框 + 填写提交 + dump 页面 HTML 供选择器发现 + 尽力抽取题录 |
| `tools/verify_resource.py` | 验证用户贴来的资源 URL 能否真正进入（而非被踢回 login） |
| `references/vpn.md` | WebVPN 技术细节（反代形态、启动器硬墙、会话时效、排错） |
| `references/catalog.md` | 171 个可检索库目录（按 10 类归类） |
| `prompts/query.md` | 各库 DOM 差异下的选择器发现工作流 |

## 依赖

- 系统 Python 3.14 + `playwright`（已装，Chromium 已缓存）；本机需有 Edge / Chrome。
- 首次缺内核：`/c/Python314/python.exe -m playwright install chromium`。
- 浏览器选择：推荐 Edge / Chrome（`--channel msedge`）；**不要用 Brave**（非 Playwright 通道，无法接管登录态）。

## 安全

- 本 skill 不读取、不存储用户密码；登录动作由用户本人在真实浏览器完成。
- `sessions/` 含登录态 cookies（等同账号密码），已被 `.gitignore` 排除，**严禁提交**。
- 仅用于本人合法科研查阅，不做突破访问限制的大规模爬取。

> 说明：本 skill 为 `cnki-auth-access`（CNKI 单库特例）的通用化升级，覆盖全部 171 个 MetaLib 库。
