# neuq-metalib-access

东北大学秦皇岛分校校园 WebVPN **接管法**检索 skill。复用用户真实登录态，检索校内 **171 个 MetaLib 数据库**（知网 CNKI、万方、维普、Web of Science、Scopus、ScienceDirect、SpringerLink、ACS、IEEE、RSC、Wiley、CAS SciFinder-n、Derwent、中外专利、ProQuest 博硕、CSSCI、NSTL 等）。

## 为什么必须"接管法"（核心约束）

校园 WebVPN（深信服反代 `vpn.neuq.edu.cn`）有两道硬墙，纯 agent 自动检索走不通：

1. **门户启动器反自动化**：「数字资源」里每个库的入口靠 JS 启动器在服务端按次签发带 `wrdrecordvisit` 令牌的代理 URL。启动器检测 `window.chrome.runtime` 区分真人与 Playwright，Playwright 接管的 Edge 该属性是只读冻结对象、刻意无 `runtime` 且不可重定义，注入 stealth 被 `non-configurable` 挡掉。**agent 自己点「知网/万方/WOS」毫无反应，必须由你手动点。**
2. **URL 编码与会话绑定**：① 裸反向代理 URL（不带 `wrdrecordvisit`）→ `DNS_RECORD_NOT_FOUND`，深信服把编码串当主机名解析，裸路径不签发资源会话；② 你在自己真 Edge 里点库拿到的令牌 URL，跨会话拿到本 agent profile 里同样进不去（被当主机名解析 / 踢回登录）。令牌必须和活的 VPN cookie **同会话**使用。

**唯一稳定可用的方法是「接管法」**：脚本拉起本机 Edge 停在门户 → **你在该窗口登录 VPN 并手动点库** → 资源页在本会话内正常打开 → agent 扫描 `context.pages` 识别带检索框的库页面并直接驱动检索。

> 两条硬约束：❌ 裸 URL 不可用（DNS 错误）；❌ 跨会话复用令牌不可用。✅ 必须在 agent 拉起的那个窗口里登录 + 点库。
> WebVPN cookie 数分钟过期，弹窗后请尽快登录 + 点库，不要闲置。

## 触发条件

用户提及需检索某具体库名（知网 / 万方 / WOS / Scopus / SciFinder / 中外专利 / …）并要检索 / 下载 / 查新时。

## 结构

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 完整说明与执行流程（含用户配合步骤、故障排查） |
| `tools/relay_query.py` | **通用接管检索主脚本**：拉起 Edge → 等你登录+点库 → 自动探测检索框、填词、提交、抽取。覆盖全部 171 库 |
| `tools/metalib_query.py` | 按贴来的资源 URL 驱动的检索/抽取（接管法不可用时作脆弱兜底） |
| `tools/campus_login.py` | 建立持久化登录态（有头窗口，用户手动登录） |
| `tools/verify_resource.py` | 验证用户贴来的资源 URL 能否真正进入（而非被踢回 login） |
| `references/vpn.md` | WebVPN 技术细节（反代形态、启动器硬墙、会话时效、排错） |
| `references/catalog.md` | 171 个可检索库目录（按 10 类归类） |
| `prompts/query.md` | 各库 DOM 差异下的选择器发现工作流 |
| `sessions/a1_wait_open_cnki.py` | 历史：A1 专利知网 novelty 验证脚本（已被 `relay_query.py` 通用化取代，仅作 CNKI 特例参考） |

## 主路径用法（接管法）

```bash
PY=/c/Python314/python.exe
REL=/c/Users/wumin/.workbuddy/skills/neuq-metalib-access/tools/relay_query.py
# 查知网某关键词：
$PY $REL --session-name neuq --library cnki --query "光催化 亚氯酸盐 二氧化氯"
# 查 WOS（不给 --query 则仅接管并 dump 页面供选择器发现）：
$PY $REL --session-name neuq --library wos --query "chlorine dioxide photocatalysis"
```

运行后窗口弹出，**你只需在该窗口内做两件事**：① 登录校园 VPN；② 在门户「数字资源」里手动点击你要查的库。之后脚本自动接管，结果写到 `sessions/<library>_result.json` 并 dump 页面 HTML 到 `sessions/<library>_page.html`。

> 若点击库后弹出「统一身份认证 / CAS」登录页，那是该库的 SSO，请也登录；登录后库页面才真正打开，脚本会自动等待（不会把登录页误判为库页）。WebVPN cookie 数分钟过期，弹窗后请尽快登录+点库。

## 依赖

- 系统 Python 3.14 + `playwright`（已装，Chromium 已缓存）；本机需有 Edge / Chrome。
- 浏览器：`--channel msedge` 复用已装 Edge，**不下载浏览器二进制**、不重装 playwright。
- 若误跑出"重装 playwright"提示：是解释器用错（用了托管 3.13），改用 `C:/Python314/python.exe`。

## 安全

- 登录动作由用户本人在真实浏览器完成，本 skill 不读取、不存储用户密码。
- `sessions/` 含登录态 cookies（等同账号密码），已被 `.gitignore` 排除，**严禁提交**。
- 仅用于本人合法科研查阅，不做突破访问限制的大规模爬取。

> 说明：本 skill 为 `cnki-auth-access`（CNKI 单库特例）的通用化升级，覆盖全部 171 个 MetaLib 库。
