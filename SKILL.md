---
slug: neuq-metalib-access
name: neuq-metalib-access
displayName: 东大秦皇岛校内库检索（VPN 混合接力）
version: 1.0.0
description: |
  通过东北大学秦皇岛分校校园 WebVPN（vpn.neuq.edu.cn）混合接力，复用用户真实登录态检索校内 171 个 MetaLib 数据库
  （知网CNKI、万方、维普、Web of Science、Scopus、ScienceDirect、SpringerLink、ACS、IEEE、RSC、Wiley、
  CAS SciFinder-n、Derwent、CNIPA/中外专利、ProQuest 博硕、CSSCI、NSTL 等）。
  当用户提到"用校内权限/学校VPN查某库""帮我查万方/WOS/知网/…""校内数据库检索""下知网/万方全文"
  或提及 MetaLib 目录中任一具体库名（见 references/catalog.md）并要检索/下载/查新时触发。
  仅限本校合法科研查阅，不突破访问限制。
author: 老吴
agent_created: true
user-invocable: true
---

# 东大秦皇岛校内库检索（VPN 混合接力）

让你用校园网身份查遍学校买下的 171 个数据库——不限知网，万方、Web of Science、Scopus、
ScienceDirect、Springer、ACS、IEEE、RSC、Wiley、SciFinder、Derwent、中外专利、ProQuest 博硕等都能用。

## 为什么必须"混合接力"（核心约束，务必先读）

东北大学秦皇岛分校的校外访问走**深信服 WebVPN 反代**（`vpn.neuq.edu.cn`）。它有一道硬墙：

- 门户「数字资源」里每个库的入口是 `href="javascript:void(0)"`，靠 JS 启动器在服务端**按次签发**带
  `wrdrecordvisit` 令牌的代理 URL；直链没有这个会话会被踢回 `vpn.neuq.edu.cn/login`。
- **启动器检测 `window.chrome.runtime` 是否存在来区分真人与 Playwright**：Playwright 接管下的 Edge 该属性是
  **只读冻结对象**，只暴露 `loadTimes/csi/app`、刻意无 `runtime` 且不可重定义；注入 stealth
  （`Object.defineProperty(window,'chrome',...)`）被 `non-configurable` 挡掉，无法伪造 `runtime`。
  结果：**智能体浏览器自己点「知网/万方/WOS」毫无反应**（无请求/无跳转/无弹窗）。
- 因此"纯 agent 自动点资源"这条路被环境堵死。可行方案是**混合接力**：
  1. **你在自己的真 Edge（有 runtime + 已登录 VPN）里点开目标库** → 生成带 `wrdrecordvisit` 的新鲜令牌代理 URL；
  2. **把该 URL 贴给智能体**；智能体用同一套持久化浏览器 profile 加载它，复用你的 VPN 会话 cookie 去检索/抽结果。

> `wrdrecordvisit` 每次点击刷新、**不可复用**；且 VPN Web 会话 cookie **几分钟就过期**。所以每批检索前都要你
> 重新在 agent 窗口登一次 VPN（cookie 落盘后关窗不影响已存，但会话本身会过期），并贴一个新鲜资源 URL。

## 适用触发

- "用校内权限查 万方 / WOS / 知网 / SciFinder / …""帮我下知网论文""学校 VPN 帮我查 Scopus"
- 提到 MetaLib 目录中任一库名（见 references/catalog.md）并要检索 / 下载 / 查新
- SmartLib 额度耗尽、又要查校内专属库或下全文时
- 与 `cnki-auth-access` 的关系：本技能是其**通用化升级**，覆盖全部 171 库；CNKI 单库场景旧技能仍可用。

## 执行流程

### 阶段 0 · 一次性登录（建立持久化会话）
```bash
PY=/c/Python314/python.exe
LOGIN=/c/Users/wumin/.workbuddy/skills/neuq-metalib-access/tools/campus_login.py
$PY $LOGIN --session-name neuq
# 窗口弹出 vpn.neuq.edu.cn 登录页 → 你登录 → 登录好后告诉智能体"登录好了"
# 智能体建哨兵文件 → 脚本保存 profile 并关窗。之后所有检索带 --session-name neuq
```
- 登录动作由你本人完成，脚本不读密码。

### 阶段 1 · 你点开目标库，贴新鲜 URL
在你自己的真 Edge（已登录 VPN）里：进门户「数字资源」→ 点目标库（如 Web of Science）→ 复制地址栏里
带 `wrdrecordvisit` 的代理 URL → 贴给智能体。

### 阶段 2 · 智能体加载并检索
```bash
Q=/c/Users/wumin/.workbuddy/skills/neuq-metalib-access/tools/metalib_query.py
V=/c/Users/wumin/.workbuddy/skills/neuq-metalib-access/tools/verify_resource.py
# 先验证 URL 还能进（可选，确认没被踢回 login）：
$PY $V "<你贴的URL>"
# 单库检索（给关键词则自动找检索框；不给则仅加载并 dump 页面供选择器发现）：
$PY $Q --start-url "<你贴的URL>" --query "二氧化氯 催化" --session-name neuq --library wos
```
- 工具会：加载 URL → 若给 `--query` 则自动探测常见检索框（`input/textarea`，匹配 search/keyword/kw/检索 等）
  并填写、提交 → 等待结果页 → dump 页面 HTML 到 `sessions/<library>_page.html` → 尽力抽取题名/作者/来源
  → 存 `sessions/<library>_result.json`。
- 因各库 DOM 不同，自动抽取可能不全；dump 的 HTML 供智能体做选择器发现或二次精准抽取（见 prompts/query.md）。

## 校园 VPN 说明
- 网页版 VPN（vpn.neuq.edu.cn）：登录后浏览器即校内网，代理出各库。
- 系统级客户端（EasyConnect/SVPN）：你先连，再跑 `campus_login.py --no-vpn` 只建 profile；浏览器继承校内网。
- 排错与细节见 references/vpn.md。

## 171 个可检索库
完整清单见 references/catalog.md（按 10 类归类）。重点库（与科研最相关）：
中国知网 CNKI(NEU00046)、万方(NEU00028)、维普(NEU00029)、ISI Web of Science(NEU00102)、
ScienceDirect(NEU00155)、Scopus(NEU00392)、SpringerLink、IEL(IEEE)、ACS、Nature、Science、Wiley、
EBSCO、CAS SciFinder-n(NEU00401)、Engineering Village(Ei/Inspec)、Derwent Innovations Index(DII)、
ProQuest 博硕、JSTOR、Taylor&Francis、MDPI、Frontiers、Cell、NSTL(NEU00251)、CSSCI(NEU00321)。

## 安全红线
- ⚠️ `sessions/` 含登录态 cookies，等同账号密码：仅本机、不进 git、不外传、不粘贴到对话/联网服务。
- `.gitignore` 已排除 `sessions/`。误操作提交后立即改密码并删 cookies。
- 仅本人合法科研查阅；不做突破访问限制的大规模爬取。cookie 几小时~几天过期，过期重登即可。

## 依赖
- 系统 Python 3.14 + `playwright`（已装，Chromium 已缓存）；本机需有 Edge/Chrome。
- 首次缺内核：`/c/Python314/python.exe -m playwright install chromium`。
- 浏览器选择：推荐 Edge/Chrome（`--channel msedge`）；**不要用 Brave**（非 Playwright 通道，无法接管登录态）。
