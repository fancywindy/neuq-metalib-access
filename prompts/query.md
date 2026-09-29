# 通用库检索驱动要点（选择器发现工作流）

各 MetaLib 库的检索页 DOM 差异很大，`metalib_query.py` 的自动探测只覆盖常见模式。下面是"自动没命中时"
由智能体据 dump 的 HTML 做选择器发现、二次驱动的流程。

## 1. 先加载、后 dump（不急于填词）
```bash
$PY metalib_query.py --start-url "<新鲜URL>" --session-name neuq --library <名> --no-query
```
工具只加载并 dump `sessions/<名>_page.html`。智能体读该 HTML，定位：
- 检索框：`input` / `textarea`，id 或 name 常含 `search / keyword / kw / q / txt / query`，
  或 placeholder 含"检索/搜索/关键词"。
- 提交钮：`button` / `input[type=submit]` / `a`，文字常含"检索/搜索/Search/Go/查询"。
- 结果容器：`#results / .result-list / table / .doc-item / #briefBox / #gridTable` 等。

## 2. 知网特例（已固化）
- 首页检索框：`textarea#txt_SearchText`；提交：`div.search-btn`（点它，或对该框按 Enter）。
- 结果页落在 kns8s：`#txt_search` + `#btnSearch`；结果抽 `#gridTable / #briefBox`。

## 3. 二次精准驱动
发现选择器后，有两种做法：
- **改 `--query` 跑**：若自动探测漏了（如框在 iframe、或需先选数据库切换），把正确选择器硬编码进
  `metalib_query.py` 的 `AUTO_FILL_JS` / 提交逻辑后重跑；
- **直接写一次性 Playwright 片段**：对特殊库（WOS 高级检索、Scopus 表单、SciFinder 反应式检索），
  由智能体临时写一段 Python 用同一 `profile_<session>` 上下文，按发现的选择器 fill+click+抽取。

## 4. 抽取与去噪
- 通用抽取：抓结果容器内 `a` 元素（题名）+ 同行作者/来源/年；按 link 或 title 去重。
- 噪声处理：知网多词检索常把相关词混入（如"压电"带出纯光催化水氧化），需人工核对题录是否真做目标反应；
  多词 AND 有时不生效（如"单原子铁 氨氮 选择性 光催化"返全噪声），应拆成更精准的短式复核。
- 跨库去重：同一文献可能在 CNKI + WOS + 万方都出现，合并结论时按 DOI/题名归一。

## 5. 输出规范
每次检索落盘 `sessions/<library>_<date>_result.json`，字段：`{library, query, count, results:[{title,authors,source,date,link}]}`；
批量查新时汇总到一份综合结论文档（参照 09-29 知网查新 + 09-28 FTO 报告的合并模式）。
