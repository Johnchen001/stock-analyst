---
name: a-share-morning-briefing
category: finance
description: >-
  A股晨间简报完整操作手册：交易日判断、行情/新闻/龙虎榜/新股数据采集（API+浏览器）、
  四大模块简报撰写规范、PDF 生成（fpdf2 中文）、微信 PDF 推送。0 基础 agent 按本文档
  即可端到端生成并交付与历史晨报一致（格式+内容密度）的 PDF 晨报。
triggers:
  - user says "发早报"
  - user says "晨间简报"
  - user says "今日早报"
  - user says "morning briefing"
  - user says "手动触发晨间简报"
  - cron job a-share-morning-briefing failure recovery
  - 需要生成 A股晨报 PDF
tags:
  - A股
  - 晨间简报
  - stock
  - finance
  - cron
  - morning-briefing
  - PDF
  - WeChat
---

# A-Share Morning Briefing (A股晨间简报) — 端到端操作手册

## 0. 目标与交付物

用户每天早上收到一份 **A股晨间简报 PDF**（微信推送）。本手册让任何 0 基础 agent
（无会话上下文、无历史记忆）直接照做即可产出**同样的晨报**：同样的四大模块结构、
同样的内容密度、同样的 PDF 版式（一页一个模块）、同样的微信交付方式。

**最终交付物（缺一不可）：**
1. PDF 文件：`~/Desktop/${YYYYMMDD}_A股晨间简报.pdf`（如 `~/Desktop/20260831_A股晨间简报.pdf`）
2. 通过微信发送该 PDF 给联系人 `o9cq800hCSIovrI8HvOMYOQ-QHAY@im.wechat`

**关键环境事实（写死，不要重新发现）：**
- Python 解释器（含 fpdf2）：`$HOME/.hermes/hermes-agent/venv/bin/python3`
- 脚本目录：`$HOME/.hermes/scripts/`
- stock-analyst profile CLI：`$HOME/.local/bin/stock-analyst`（其模型是 DeepSeek）
- 微信联系人 ID：`o9cq800hCSIovrI8HvOMYOQ-QHAY@im.wechat`
- 运行环境：macOS（无 `timeout` 命令，脚本内用 perl alarm 或 python subprocess timeout）

---

## 1. 快速启动（最短路径，3 步）

若只需"立即生成今天的晨报并推送到微信"，按优先级选：

### 方式 A：运行现成脚本（推荐，最快）
```bash
bash ~/.hermes/scripts/morning_briefing.sh
```
- 内部自动：判断交易日（周末静默退出）→ 调 stock-analyst profile 生成简报 →
  生成 PDF → 微信发送。
- 耗时 5-10 分钟（取决于 DeepSeek 响应速度）。用 `background=true` + `notify_on_complete=true` 跑。
- 若 stock-analyst 的模型（DeepSeek）不可用，改用 `bash ~/.hermes/scripts/morning_briefing_current.sh`
  （走当前 profile 的模型）。

### 方式 B：全手动（脚本失败/模型全挂时的兜底，见 §5）
自己收集数据 → 写 markdown → 转 PDF → 发微信。本手册 §3-§7 是完整说明。

### 方式 C：本会话直接生成（agent 模式）
当前会话本身就是 LLM：按 §3 收集数据、§4 写 markdown、§6 转 PDF、§7 发送。
此方式不依赖 stock-analyst profile，最可控。

---

## 2. 交易日判断（第一步必做）

**规则：周一至周五才发；周六周日静默跳过；法定节假日视情况（脚本只查星期，不查法定假日，
长假后第一个交易日必须覆盖整个假期新闻）。**

```bash
DOW=$(date +%u)   # 1=周一 ... 7=周日
if [ "$DOW" -gt 5 ]; then echo "周末，跳过"; exit 0; fi
```

脚本（方式 A）已内置此判断；方式 B/C 也要先确认今天是不是交易日（周末直接告诉用户"今日非交易日，不生成"）。

---

## 3. 数据收集（方式 B/C 用）

### 3.1 指数行情（curl API，最快）

```bash
# A股主要指数（上证/深成/创业板/科创50/沪深300/中证500/北证50）
curl -s "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14&secids=1.000001,0.399001,0.399006,1.000688,0.000300,0.399905,0.899050"

# 隔夜美股（纳斯达克/道琼斯/标普500）——晨报"隔夜美股"必备
curl -s "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14&secids=100.NDX,100.DJI,100.SPX"
```

字段含义：f2=最新价, f3=涨跌幅%, f4=涨跌额, f12=代码, f14=名称。

**注意**：晨报在 07:30-08:00 生成，A股尚未开盘，指数接口返回的是**昨日收盘数据**，
写简报时表述为"昨日上证收于 XXX，涨跌 X%"。

### 3.2 昨日涨跌幅排名（涨跌幅榜）

盘前 f3 对个股返回 "-"，**必须用 `fid=f171`（昨日涨跌幅）排序**，绝不能用 f3：

```bash
# 昨日涨幅前10
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f171&fs=m:0+t:6,m:1+t:2,m:1+t:23&fields=f12,f14,f18,f170,f171"
# 昨日跌幅前10（po=0 升序）
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=0&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f171&fs=m:0+t:6,m:1+t:2,m:1+t:23&fields=f12,f14,f18,f170,f171"
```

字段：f12=代码, f14=名称, f18=昨收, f170=昨日涨跌额, f171=昨日涨跌幅%。

**clist 字段速查：**
| 字段 | 含义 | 盘前行为 |
|------|------|---------|
| f12 | 股票代码 | 始终可用 |
| f14 | 股票名称 | 始终可用 |
| f2 | 最新价 | 返回 "-" |
| f3 | 当日涨跌幅 | 返回 "-" |
| f18 | 昨收 | 始终可用 |
| f170 | 昨日涨跌额 | ✅ 可用 |
| f171 | 昨日涨跌幅% | ✅ 排序用它 |

### 3.3 新闻（昨夜今晨）

**首选：新浪财经 7x24 直播** `https://finance.sina.com.cn/7x24/`
- 实时新闻流，按时间倒序，一次加载大量新闻
- 点底部"A股"标签筛选；15:00 附近有收评、09:25 有开盘综述
- 比东财更精炼，无需滚动大量无关内容

**备选：东方财富证券聚焦** `https://finance.eastmoney.com/a/czqyw.html`
- 精选最新新闻列表（含摘要+时间戳）+ 网友点击排行榜（热点）

**API 可靠性警告**：东财 push2 API 在部分网络环境下会 TLS 握手成功但返回空
（curl exit 52）或被限流。**空返回时最多重试 1 次，立即切浏览器方式**
（同一批 URL 用 browser_navigate 打开，走浏览器 IP/UA 更稳）。

### 3.4 龙虎榜（昨日大涨股分析的数据来源之一）

```bash
# 东财龙虎榜（默认显示最近交易日）
browser_navigate("https://data.eastmoney.com/stock/tradedetail.html")
```
表格含：股票、价格、涨跌幅、净买入、机构活跃度、上榜原因。
详细字段见 `references/eastmoney-stock-ranking-api.md`。

### 3.5 新股日历（今日关注推荐的"打新"部分）

```bash
browser_navigate("https://data.eastmoney.com/xg/xg/default.html")
```
或 `https://data.eastmoney.com/xg/`。看三件事：
- **今日申购**（名称+代码+申购日期+发行价+所属细分领域）
- **今日中签缴款**（名称+代码）
- **即将上市**（名称+代码+上市日期）

### 3.6 资金流向（可选补充）

同花顺 `https://stock.10jqka.com.cn/` 首页有板块排名、个股资金流、龙虎榜入口。
也可从东财个股资金流接口获取，非必需模块，时间紧可跳过。

---

## 4. 简报撰写规范（核心！格式必须与历史晨报一致）

### 4.1 文件与结构

- 文件名：`/tmp/morning_briefing_${YYYYMMDD}.md`
- 第一行：`# A股晨间简报`
- 第二行：`## YYYY年MM月DD日 周X`
- 之后是**四大模块，每个模块用 `## ` 一级标题**（PDF 每个 `## ` 独占一页）：
  1. `## 一、新闻模块`
  2. `## 二、省市投资动态`
  3. `## 三、昨日大涨股分析`
  4. `## 四、今日关注推荐`
- 子项用 `### `，列表用 `- `，表格用 `|` 分隔
- 结尾：`> 免责声明` 引用块
- **markdown 里禁止使用 `**` 加粗**（PDF 生成器会剥离，但历史版本曾因 `**` 残留被用户投诉，直接不写最干净）

### 4.2 模块内容要求（每条都是用户明确要求过的，缺一不可）

**一、新闻模块（至少 10 条，总计 600-800 字）**
- 隔夜美股三大指数涨跌 + 科技股/中概股表现（数据来自 §3.1）
- 国际重大事件（地缘政治、汇率、大宗商品）
- 国内政策/经济数据（央行、证监会、发改委、统计局等）
- 产业重大新闻（半导体、新能源、AI 等）
- **每一条新闻末尾加括号注明对 A 股相关板块的利好/利空影响**，如
  `（利好：半导体国产替代）`
- **假期后第一个交易日：新闻覆盖整个假期期间**，不是只写昨天

**二、省市投资动态（约 400 字，重点江浙沪）**
- 每个省至少 3 个细分领域（半导体、新能源、生物医药、人工智能、低空经济、光通信等）
- **每个细分领域必须对应到具体上市公司：名称+6 位代码**，如
  `上海：人工智能 — 商汤科技(00020.HK) ...` 或 `江苏：半导体 — 长电科技(600584)`
- 禁止只写"某某省大力发展人工智能"这种空话

**三、昨日大涨股分析（至少 5 支，每支 150 字以上）**
- 具体股票：名称+代码+涨幅（数据来自 §3.2 涨跌幅榜 / §3.4 龙虎榜）
- 详细分析上涨原因：基本面/消息面/资金面三个维度
- **必须用真实数据**（涨跌幅榜、龙虎榜提取），禁止编造
- 拒绝仙股/垃圾股（市值过小、无成交量的不选）

**四、今日关注推荐（至少 10 支，分 5 类）**
- **新股申购**：细分领域+新股名称+代码+申购日期+发行价（来自 §3.5）
- **即将上市新股**：名称+代码+上市日期
- **上涨潜力股**：代码+看好逻辑（1-2 句）
- **优质股/业绩预增股**：代码+逻辑
- **防御型/高股息标的**：代码+逻辑

### 4.3 语言与语气

- 语气：客观、专业、中立
- **禁止任何买卖建议**（"建议买入""可重仓"等一律不写；可写"关注""跟踪"）
- 每只股票必须 名称+6 位代码
- 每个数据点注明来源（据东方财富/据公司公告/据新浪财经）
- 全文中文，数字用半角

---

## 5. 生成方式对比（三种路径，按需选）

| 路径 | 命令/做法 | 适用场景 |
|------|----------|---------|
| A 脚本 | `bash ~/.hermes/scripts/morning_briefing.sh` | 默认；stock-analyst(DeepSeek) 正常时 |
| A' 脚本(当前profile) | `bash ~/.hermes/scripts/morning_briefing_current.sh` | DeepSeek 挂时，走当前会话模型 |
| B 手动 | §3 收数据 → §4 写 md → §6 转 PDF → §7 发送 | 脚本超时/失败，agent 自己干 |
| C 本会话 | 同 B，但由当前 agent 直接执行 | 用户说"用当前会话发早报" |

**脚本内部逻辑（morning_briefing.sh，理解故障必读）：**
1. `date +%u` 判断周末 → 静默退出
2. `export HERMES_HOME=$HOME/.hermes/profiles/stock-analyst`，调
   `$HOME/.local/bin/stock-analyst chat -q "<完整简报 prompt>"` 生成 markdown
   （prompt 内嵌四大模块要求，见脚本 33-66 行）
3. 输出写 `/tmp/morning_briefing_${YYYYMMDD}.md`；检测到 `[SILENT]` → 非交易日退出
4. `gen_briefing_pdf.py` 转 PDF 到 `~/Desktop/${YYYYMMDD}_A股晨间简报.pdf`
5. `send_wechat_pdf_retry.py` 发微信

**脚本时间限制的实现（macOS 无 timeout 命令）：**
- `morning_briefing.sh` 用 `perl -e 'alarm shift; exec @ARGV' 600 ...`
  ⚠️ **已知缺陷：`exec` 会替换 perl 进程导致 alarm 失效**（实测 07:30 的 job 拖到 09:54-11:33 才完成）。
  手动触发时优先用 `morning_briefing_current.sh`（python subprocess timeout=600，真正生效）
  或后台跑 + 自己 poll。
- 手动生成时**不要**依赖 perl alarm；用 python subprocess timeout 或后台进程管理。

---

## 6. PDF 生成（markdown → PDF）

```bash
$HOME/.hermes/hermes-agent/venv/bin/python3 \
  $HOME/.hermes/scripts/gen_briefing_pdf.py \
  /tmp/morning_briefing_${YYYYMMDD}.md \
  $HOME/Desktop/${YYYYMMDD}_A股晨间简报.pdf
```

**gen_briefing_pdf.py 行为（写 markdown 前必读，避免版式翻车）：**
- **每个 `## ` 一级标题独占一页**（首个 `## ` 前先 add_page 一次）
- 自动 **剥离所有 `**`**（clean_text）——所以 markdown 里别写 `**`，写了也会被删
- emoji 映射为文字（📊→[图表] 等），STHeiti 无 emoji 字形
- 表格 `| a | b |` 渲染为结构化文本：`  Header: Cell | Header: Cell`（分隔行跳过）
  → **markdown 里表格列头要写清楚**，PDF 里才有意义
- 中文字体：`/System/Library/Fonts/STHeiti Light.ttc`（常规）、
  `STHeiti Medium.ttc`（粗体）
- 封面页：居中大标题"A股晨间简报"+ 日期 + 灰色免责声明
- 页脚自动页码"第 X/Y 页"

**fpdf2 依赖**：必须装在 Hermes venv 里（默认没有）：
```bash
$HOME/.hermes/hermes-agent/venv/bin/pip install fpdf2
```
缺它报 `ModuleNotFoundError: No module named 'fpdf'`。

**生成后验证**：`ls -la` 确认 PDF 存在且 >0 字节；建议再确认大小合理（历史晨报
PDF 约 150-200KB）。PDF 生成失败时回退为纯文本发送（见 §7）。

---

## 7. 微信 PDF 发送

```bash
# 带指数退避重试的发送器（推荐；12 次尝试，30s 基数）
$HOME/.hermes/hermes-agent/venv/bin/python3 \
  $HOME/.hermes/scripts/send_wechat_pdf_retry.py \
  "o9cq800hCSIovrI8HvOMYOQ-QHAY@im.wechat" \
  "$HOME/Desktop/${YYYYMMDD}_A股晨间简报.pdf"
```

- 简单版：`send_wechat_pdf.py <chat_id> <pdf_path>`（无重试）
- 内部走 iLink Bot API；PDF 走 send_document，图片走 send_image_file
- **限流错误**：`iLink sendmessage rate limited; cooldown active for 30.0s` —
  retry 脚本自动处理；手动处理：等 60s 冷却再发，或
  `kill $(pgrep -f "gateway.*run") 2>/dev/null` 清掉旧 gateway 再发
- **Gateway 冲突**：`Weixin bot token already in use (PID XXXX)` → 同上 kill 后重试
- PDF 发送失败且无法恢复时：把 markdown 内容作为纯文本发微信（比不发强），
  并告知用户 PDF 生成失败

---

## 8. 定时任务（cron）配置（参考，当前可能已删除）

历史 cron 配置（如需重建）：
- Job：`a-share-morning-briefing`，schedule `30 7 * * 1-5`（工作日 07:30 北京时间）
- 类型：no_agent 脚本 job，script=`morning_briefing.sh`
- deliver：origin（脚本自己负责发微信，stdout 保持为空避免重复推送）
- **stock-analyst profile 里还有历史版本**：`每日A股早报推送`(56a648c7dd68, LLM job)、
  `自选股日报推送`(164824b0072f, 工作日 08:00) —— 跨 profile 检查定时任务时
  用 `cat ~/.hermes/profiles/*/cron/jobs.json`，`cronjob list` 只显示当前 profile

---

## 9. 故障排查速查表

| 症状 | 根因 | 处理 |
|------|------|------|
| 脚本跑很久没结果（>10min） | perl alarm 失效 + DeepSeek 慢 | kill 进程，换 `morning_briefing_current.sh` 或手动路径 B |
| `ModuleNotFoundError: fpdf` | fpdf2 未装 | venv pip install fpdf2 |
| curl 返回空/exit 52 | 东财 API 限流/封 IP | 最多重试 1 次，切浏览器方式 |
| 个股 f2/f3 全是 "-" | 盘前无实时数据 | 用 fid=f171 取昨日涨跌幅 |
| 微信发送 rate limited | iLink 冷却 | retry 脚本自动退避；手动等 60s |
| `Weixin bot token already in use` | 多个 gateway 抢占 | kill $(pgrep -f "gateway.*run") |
| DeepSeek API 全挂 | 服务商故障 | 用当前会话模型（方式 C）直接生成 |
| 简报内容空/只有几行 | stock-analyst 模型超时/未响应 | 手动路径 B：自己收数据写简报 |
| 假期后第一天的晨报缺假期新闻 | 模型只写了昨天 | 新闻模块显式要求覆盖整个假期 |

---

## 10. 用户偏好红线（违反=返工，务必逐条遵守）

1. 交付物 = **PDF 文件 + 微信推送**，不是聊天文本
2. **PDF 一个模块一页**（每个 `## ` 独占一页）
3. **PDF 内禁止出现 `**` 残留**；表格渲染为结构化文本而不是被丢弃
4. 新闻模块**每条带板块利好/利空标注**
5. **假期后新闻覆盖整个假期**
6. 省市动态**细化到细分领域+具体公司（名称+代码）**，禁止空泛
7. 大涨股分析**至少 5 支、每支 150 字以上、真实数据**
8. 今日关注推荐**至少 10 支**，新股申购必须**细分领域+名称+代码+申购日期+发行价**
9. 科创板/创业板半导体等推荐**必须具体代码+名称**，不能只写概念
10. 语气客观中立，**禁止买卖建议**；每只股票名称+6 位代码

---

## 11. 相关参考文件

- `references/briefing-sources-and-format.md` — 数据源明细 + 通用内容模式（避险模式/芯片股/ETF 放量/假期缺口）
- `references/eastmoney-stock-ranking-api.md` — 东财排序 API 字段详解
- `references/wechat-pdf-delivery.md` — 微信发送细节 + send_weixin_direct API 签名
- `references/watchlist-daily-report.md` — 自选股日报（同 profile 的兄弟任务，勿混淆）
