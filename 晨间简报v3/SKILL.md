---
name: a-share-morning-briefing
category: finance
description: >-
  A股晨间简报完整操作手册：交易日判断、行情/新闻/龙虎榜/新股数据采集（API+浏览器）、
  五模块（隔夜市场与重大新闻/昨日A股收盘回顾/省市投资动态/大涨股分析/今日关注）撰写规范、
  公司元数据驱动个股分析、PDF 生成（fpdf2 中文）、微信 PDF 推送。0 基础 agent 按本文档
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
（无会话上下文、无历史记忆）直接照做即可产出**同样的晨报**：同样的五模块结构、
同样的内容密度、同样的 PDF 版式（v2 蓝白：每章一页、溢出自适应压排）、同样的微信交付方式。

**最终交付物（缺一不可）：**
1. PDF 文件：`~/Desktop/暑假/投资分析/晨间简报/${YYYYMMDD}_A股晨间简报.pdf`
2. 通过微信发送该 PDF 给联系人 `<YOUR_CHAT_ID>@im.wechat`

**PDF 版式 = v2 蓝白（2026-10-28 用户逐条确认定稿）**：宋体小四 12pt、蓝白配色、每章新起一页、
章节自适应压排、模块一自动编号、大涨股分块、分组小标题加粗。细则见 `references/pdf-layout-spec.md`，
渲染器 `gen_briefing_pdf_v2.py`。旧版深红金封面已废弃，不要再产出。

**关键环境事实（写死，不要重新发现）：**
- Python 解释器（含 fpdf2）：`$HOME/.hermes/hermes-agent/venv/bin/python3`
- 脚本目录：`$HOME/.hermes/scripts/`
- stock-analyst profile CLI：`$HOME/.local/bin/stock-analyst`（其模型是 DeepSeek）
- 微信联系人 ID：`<YOUR_CHAT_ID>@im.wechat`
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

**盘中补发（实际时间晚于 09:15）**：此时 `ulist` 的 `f2/f3` 是当日盘中价，**不能当昨收**。昨收与昨日涨跌幅改取
`push2his.eastmoney.com/api/qt/stock/kline/get?secid=<secid>&klt=101&lmt=3&fields2=f51,f53,f59`，
挑日期等于上一交易日的那根（f53 收盘、f59 涨跌幅）；简报首段注明「实际生成时间 HH:MM，今日为盘中数据」。
板块同理：`clist` 的 `f3` 只给当日，昨日板块涨跌要对已知 BK 代码逐个跑 `secid=90.BK####` 的 kline
（半导体 BK1036、汽车零部件 BK0481、通用设备 BK0545、专用设备 BK0533、通信设备 BK0448、军工 BK0490、
消费电子 BK1038、电池 BK1033、白酒 BK0896、银行 BK0475、证券 BK0473、影视院线 BK0485、有色金属 BK0478），
20 个板块约 20 次请求、10 秒内跑完，比等 `clist` 板块榜靠谱（该榜盘中常返回空）。

### 3.2 昨日涨跌幅排名（涨跌幅榜）

⚠️ **f171 不是「昨日涨跌幅」，而是 5 日涨跌幅（2026-10-30 实测）**：clist 里 `f170`=成交额、
`f171`=5日涨跌幅。实测鄂尔多斯(600295) f171=15.42%，而其 10-29 单日涨跌幅为 -0.20%；
强一股份(688809) f171=12.68%，10-29 实际 -6.74%。**盘前/盘中用 fid=f171 排序会把「5日强势股」
误当成「昨日大涨股」，直接导致模块四整节写错标的。**

正确做法（按优先级）：
1. **昨日大涨股/涨停结构：直接取涨停池** `push2ex.eastmoney.com/getTopicZTPool?...&date=YYYYMMDD`
   （显式上一交易日），字段含 `zdp` 单日涨幅、`lbc` 连板数、`fund` 封单额、`hybk` 行业，
   再对入选个股跑 `push2his` kline 取当日收盘价/换手（`f51,f53,f59,f61`）。
2. 板块昨日涨跌：对 `secid=90.BK####` 跑 kline 取 `2026-MM-DD` 那根的 f59，**不要**用 clist f171；
   东财限流时逐只串行 + 1.5s 间隔重试。
3. 全市场涨跌家数：涨停池与跌停池的 `pool` 长度（`getTopicZTPool` / `getTopicDTPool`），
   可直接给出「涨停 N 家、跌停 M 家」及环比变化。

以下旧接口仅作参考（排序结果不可信）：

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
| f170 | 成交额（元） | ✅ 可用 |
| f171 | **5 日涨跌幅%**（非昨日！） | ✅ 可用 |

### 3.3 新闻（昨夜今晨）

**首选：新浪财经 7x24 直播** `https://finance.sina.com.cn/7x24/`
- 实时新闻流，按时间倒序，一次加载大量新闻
- 点底部"A股"标签筛选；15:00 附近有收评、09:25 有开盘综述
- 比东财更精炼，无需滚动大量无关内容

**备选：东方财富证券聚焦** `https://finance.eastmoney.com/a/czqyw.html`
- 精选最新新闻列表（含摘要+时间戳）+ 网友点击排行榜（热点）

**API 可靠性警告 → 恢复阶梯（按序做，别一跳就上浏览器）**：东财 push2 会 TLS 握手成功但返回空
（curl exit 52）、`RemoteDisconnected` 或被限流；urllib 被拒时 curl 常常能通，反之亦然。
所有 push2 接口（§3.1 指数、§3.2 涨跌幅榜、元数据 stock/get、板块 clist/slist）都适用：

1. 同一 URL 重试 1 次。
2. **换主机**（只换域名，path/参数不动）：`push2` → `push2delay`（延时行情，行情/指数/行业板块/成分股字段齐全，晨报与估值对比完全够用）→ `82.push2`。
3. **换客户端**：用 `curl -s -m 12 -A "<浏览器UA>"` 重取同一 URL（urllib 挂起 17s+ 而 curl 1s 内返回是常见情形）。
4. 以上都不行才用 `browser_navigate`；cron 里尽量避免浏览器（见 §5 的 600s 超时问题）。

把「主机列表 + curl 回退」一次性写进脚本（`scripts/collect_stock_meta.py` 已实现），不要每轮手切。
字段级速查（stock/get 元数据字段、板块接口、F10 报表排序列坑）见 `references/eastmoney-stock-ranking-api.md`。

### 3.4 龙虎榜（昨日大涨股分析的数据来源之一）

```bash
# 东财龙虎榜（默认显示最近交易日）
browser_navigate("https://data.eastmoney.com/stock/tradedetail.html")
```
表格含：股票、价格、涨跌幅、净买入、机构活跃度、上榜原因。
详细字段见 `references/eastmoney-stock-ranking-api.md`。

**龙虎榜拿不到时不要卡住模块四**：`RPT_DAILYBILLBOARD_DETAILSNEW` 对某些交易日会返回
`result.data: []`（榜单未出或接口限流），盘中补发尤其常见。此时不要反复换参数死磕，也不要把
它写进报告当作有数据：改用 §5.1 的涨停池（`getTopicZTPool?date=YYYYMMDD`，带 `hybk` 行业与
`fund` 封单额）做强势板块与个股归因，并在报告里明写「龙虎榜未获取」。同理，新股「即将上市」
日历查不到就写「未获取」，**不要臆造接口名**（`RPT_IPO_LATESTMARKET` 之类不存在的报表名只会返回
`报表配置不存在`）。

### 3.5 新股日历（今日关注推荐的"打新"部分）

```bash
browser_navigate("https://data.eastmoney.com/xg/xg/default.html")
```
或 `https://data.eastmoney.com/xg/`。看三件事：
- **今日申购**（名称+代码+申购日期+发行价+所属细分领域）
- **今日中签缴款**（名称+代码）
- **即将上市**（名称+代码+上市日期）

**"细分领域"取法（2026-09-14 实测）：** 东财搜索 jsonp 对被申购新股的相关性极差（返回当天大盘文章），
不要用它凑。**直接对申购中的新股代码跑 `collect_stock_meta.py <代码>`——F10 ORGINFO 在上市前就能取到
行业/主营/省份/员工/实控人/最近一期ROE**（行情类字段为空属正常）。写表时用"主营"压缩成一句话填细分领域。

### 3.6 资金流向（可选补充）

同花顺 `https://stock.10jqka.com.cn/` 首页有板块排名、个股资金流、龙虎榜入口。
也可从东财个股资金流接口获取，非必需模块，时间紧可跳过。

---

### 3.7 公司元数据采集（强制！所有个股分析的地基，2026-09-12 用户要求）

**用户原话："以后分析的信息源不能只来自那些文章，要从公司的元数据中分析得来。"**

只要报告里要写某只股票（模块三/四的大涨股、模块五的关注推荐、自选股日报），**先跑这条命令**：

```bash
python3 ~/.hermes/scripts/collect_stock_meta.py 600584 002371 920212 --json /tmp/meta_$(date +%Y%m%d).json
```
- 一次调用覆盖全部代码（不要一只一只调）；单只 2-5s，内部 6 线程 + 多源降级。
- 代码用空格分隔；多时 `--file /tmp/codes.txt`；`--no-push2` 跳过限流源（更快）。
- 沪/深/北交所通用（北交所 92/43/83/87/88 开头自动识别）。

输出每只股票一段元数据，字段与分析用途：

| 元数据 | 用途 |
|--------|------|
| 行业(EM2016)/主营 | 板块坐标系、题材真伪（主营里有没有这块业务） |
| 总市值/流通市值 | 体量档位（<50 亿易炒 / >500 亿机构定价） |
| PE(TTM)/PE(动)/PB + 同业中位数 + 市值相近可比公司 | 估值相对位置（个股/同业中位 = 倍数） |
| 近 3 期营收·归母·扣非·研发及同比 | 成长与加速度、利润质量（扣非 vs 归母） |
| 毛利率/净利率/ROE/资产负债率/流动比/速动比 | 盈利能力与财务风险 |
| 每股经营现金流 | 盈利含金量 |
| 股东户数及环比 | 筹码集中（户数降）/ 散户涌入（户数大增） |
| 十大流通股东机构家数 + 占流通比 | 机构定价 vs 游资情绪定价 |
| 最近 6 条公告 | 事件驱动导火索（增发/回购/扩产/激励/减持），比新闻转述硬 |

**结论必须三选一并给依据**（详规：`references/company-metadata-analysis.md`）：
1. 基本面驱动 —— 营收与净利同比双增且加速 + 毛利率稳定/提升 + PE < 同业中位 1.5 倍
2. 题材/资金驱动（无基本面支撑）—— 业绩下滑/亏损/扣非为负 + PE > 同业中位 2 倍 + 无新公告
3. 混合（预期先行）—— 业绩改善但估值已透支

**硬规则**：每只股票必须带【元数据】段；字段取不到写「未获取」，绝不编造；亏损股 PE 写"亏损/不适用"，
改用 PB/PS；港股美股币种不同不得与 A 股同业直接混比。**新闻/文章只能当催化剂，不能当分析主体。**

---

## 4. 简报撰写规范（核心！格式必须与历史晨报一致）

### 4.1 文件与结构

- 文件名：`/tmp/morning_briefing_${YYYYMMDD}.md`
- 第一行：`# A股晨间简报`
- 第二行：`## YYYY年MM月DD日 周X`
- 之后是**五模块，每个模块用 `## ` 一级标题**（PDF 每个 `## ` 独占一页，内容溢出自动续页）：
  1. `## 一、隔夜市场与重大新闻`
  2. `## 二、昨日（M月D日）A股收盘回顾`
  3. `## 三、省市投资动态（江浙沪）`
  4. `## 四、昨日（M月D日）大涨股分析`
  5. `## 五、今日（M月D日）关注与推荐`
  ⚠️ 旧的"四大模块"版式（新闻模块/省市/大涨股/关注）已被取代：现行确认版把"隔夜市场与重大新闻"与
  "昨日收盘回顾"拆成两页，与用户目录里的 `~/Desktop/暑假/投资分析/晨间简报/早报生成指南.md` 及权威参考
  `20260730_A股晨间简报.pdf` 一致。模块二务必含：主要指数（收报点位+涨跌幅）、港股、昨日强势板块与
  下跌板块（各带个股名称+6位代码+涨跌幅）。
- 子项用 `### `，列表用 `- `，表格用 `|` 分隔
- 结尾：`> 免责声明` 引用块
- **markdown 里禁止使用 `**` 加粗**：v2 渲染器不解析 `**`，会原样当普通字符输出；粗体由版式规则决定
  （章节标题/股票名/分组小标题/元数据·判定·事件标签），markdown 里只写纯文本
- v2 版式下**每个 `##` 新起一页**；某章零星溢出时渲染器会自动压行距塞进一页（0.96→0.80，字号不变），压不进才跨页 —— 所以不要为了"一页装下"去删内容或缩字号

### 4.2 模块内容要求（每条都是用户明确要求过的，缺一不可）

**一、隔夜市场与重大新闻（至少 10 条，总计 600-800 字）**
- 隔夜美股三大指数涨跌 + 科技股/中概股表现（数据来自 §3.1）
- 国际重大事件（地缘政治、汇率、大宗商品）
- 国内政策/经济数据（央行、证监会、发改委、统计局等）
- 产业重大新闻（半导体、新能源、AI 等）
- **每一条新闻末尾加括号注明对 A 股相关板块的利好/利空影响**，如
  `（利好：半导体国产替代）`
- **假期后第一个交易日：新闻覆盖整个假期期间**，不是只写昨天

**二、昨日（M月D日）A股收盘回顾**
- 主要指数：收报点位 + 涨跌幅（上证/深证/沪深300/上证50/创业板/科创50/中证500/中证1000）+ 港股（恒指/恒生科技）
- 昨日强势板块与下跌板块：各带具体个股 名称+6位代码+涨跌幅；写明结构分化（谁强谁弱、涨停家数较前一日增减）
- 数据来自 §2 指数接口 / §3.2 涨跌幅榜 / §3.4 龙虎榜

**三、省市投资动态（约 400 字，重点江浙沪）**
- 每个省至少 3 个细分领域（半导体、新能源、生物医药、人工智能、低空经济、光通信等）
- **每个细分领域必须对应到具体上市公司：名称+6 位代码**，如
  `上海：人工智能 — 商汤科技(00020.HK) ...` 或 `江苏：半导体 — 长电科技(600584)`
- 禁止只写"某某省大力发展人工智能"这种空话

**四、昨日（M月D日）大涨股分析（每日精选 5 只，每只 150 字以上）** ⚠️ 必须先跑 §3.7 元数据采集
- v2 版式下每只渲染成独立块：序号 + 股票名（15pt 加粗）+ 代码 + 涨幅 + 行情行，
  再往下【元数据】【判定】【事件】三段**各起一行**（用户 2026-10-28 明确要求）
- 具体股票：名称+代码+涨幅（数据来自 §3.2 涨跌幅榜 / §3.4 龙虎榜）
- **每支必须带【元数据】段**：行业/主营 + 总市值 + PE(TTM)（含同业中位对标倍数）+ PB + 最近一期营收与归母净利同比 + 毛利率/ROE/资产负债率 + 股东户数环比 + 机构持仓占比
- **每支必须有【判定】**：基本面驱动 / 题材资金驱动（无基本面支撑）/ 混合（预期先行），并给一句话依据
- 【事件】才写新闻/公告催化剂（取元数据里的最近公告标题优先）
- **必须用真实数据**（元数据脚本输出 + 涨跌幅榜 + 龙虎榜），禁止编造；字段缺失写"未获取"
- 拒绝仙股/垃圾股（总市值过小、无成交量的不选，剔除依据要写出来）
- 只写"受XX消息刺激涨停"而无元数据支撑 = 返工
- **末尾加一行「昨日判定验证」**：把前一份报告里判为题材资金驱动（无基本面支撑）的标的与随后一日走势对照，一致或相悖各写一句（例：前期判为无基本面支撑的高位连板股，次日跌停 -9.99%，与判定一致）。这是元数据方法的自检，让判定不沦为事后叙事

**五、今日（M月D日）关注与推荐（至少 10 支，分 5 类）**
- **新股申购**：细分领域+新股名称+代码+申购日期+发行价（来自 §3.5）
- **即将上市新股**：名称+代码+上市日期
- **上涨潜力股**：代码+看好逻辑（**逻辑要落到元数据字段**：PE/PB 与同业中位对比、营收净利同比、毛利率趋势、股东户数变化）
- **优质股/业绩预增股**：代码+最近一期业绩元数据（营收/净利同比、ROE）+ 逻辑
- **防御型/高股息标的**：代码+PE/PB/资产负债率/现金流元数据+ 逻辑

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
4. `gen_briefing_pdf_v2.py` 转 PDF 到 `~/Desktop/暑假/投资分析/晨间简报/${YYYYMMDD}_A股晨间简报.pdf`
5. `send_wechat_pdf_retry.py` 发微信

**脚本时间限制的实现（macOS 无 timeout 命令）：**
- `morning_briefing.sh` 用 `perl -e 'alarm shift; exec @ARGV' 600 ...`
  ⚠️ **已知缺陷：`exec` 会替换 perl 进程导致 alarm 失效**（实测 07:30 的 job 拖到 09:54-11:33 才完成）。
  手动触发时优先用 `morning_briefing_current.sh`（python subprocess timeout=600，真正生效）
  或后台跑 + 自己 poll。
- 手动生成时**不要**依赖 perl alarm；用 python subprocess timeout 或后台进程管理。

---

### 5.1 两份报告同日交付（用户说"给我今日的两份早报"）

用户把「A股晨间简报 + 自选股日报」当一次交付。按序做完再回报，不要只交一份、也不要边做边问：

⚠️ **只点名一份时只做一份**：用户单独说"生成今日早报"或"生成自选股日报"时，只生成并推送那一份（微信重复推送=骚扰），
在回报末尾问一句是否补另一份；擅自多推一条比少推更糟。

1. **先确认日期与既有产物**：`date '+%Y-%m-%d %A %H:%M'`；`ls` 两个输出目录
   （`~/Desktop/暑假/投资分析/晨间简报/`、`~/Desktop/暑假/投资分析/自选股日报/`）。当日 PDF 已存在且已推送 →
   先问用户再决定是否重发（避免微信重复轰炸）；日期已变 → 按新日期全流程重做，**绝不复用上次会话的"昨日"数字**。
   周末/节假日 → 直接说明非交易日；用户仍要，就按"上一个交易日"口径生成并在报告里写明。
2. **一次采集全量数据**（同一条 terminal 调用内可并行）：
   - 早报基础件：`python3 ~/.hermes/profiles/stock-analyst/scripts/collect_morning_data.py`
     （指数/美股/港股/新浪7x24新闻/新股日历，约 3s）
   - 昨日涨停池：`push2ex.eastmoney.com/getTopicZTPool?...&date=YYYYMMDD`（显式指定上一交易日，避开"最近交易日≠昨日"的坑）；
     龙虎榜：`RPT_DAILYBILLBOARD_DETAILSNEW`（含净买额与上榜原因，用于交叉验证涨幅）
   - 元数据（§3.7）：大涨股 ≥5 只 + 自选股 4 只 + 江浙沪代表个股，**一条 `collect_stock_meta.py` 调用全包**（带 `--json` 落盘备查）
3. **写两份 markdown**：早报按 §4；自选股日报按下文 §11 的 `references/watchlist-daily-report.md` 六模块。
   派生指标（PE/PB 相对同业倍数、股息率、同比加速）**在生成脚本里算好再套进文本**，不手算。
4. **两份 PDF + 页数校验**：早报 `gen_briefing_pdf_v2.py`（v2 蓝白），自选股 `gen_daily_stock_report.py`；页数预期见 §6。
5. **保存**：`~/Desktop/暑假/投资分析/晨间简报/YYYYMMDD_A股晨间简报.pdf`、
   `~/Desktop/暑假/投资分析/自选股日报/自选股日报_YYYYMMDD.pdf`
6. **推送**：先早报 → `sleep 40` → 再自选股（iLink 30s 冷却是全局的，两次间隔 ≥35s）；
   两条都要看到 `✅ PDF sent` 才算完成，回报时给两个绝对路径 + 关键结论，不要复述流程。

---

## 6. PDF 生成（markdown → PDF，v2 蓝白版式）

**现行渲染器：`gen_briefing_pdf_v2.py`（2026-10-28 定稿）。** `gen_briefing_pdf.py` 是 v1 旧版式
（深色封面 / 9pt 正文），只作回退，新产出不要用。

```bash
$HOME/.hermes/hermes-agent/venv/bin/python3 \
  $HOME/.hermes/scripts/gen_briefing_pdf_v2.py \
  /tmp/morning_briefing_${YYYYMMDD}.md \
  "$HOME/Desktop/暑假/投资分析/晨间简报/${YYYYMMDD}_A股晨间简报.pdf"
```

### 6.1 版式要点（完整参数表见 `references/pdf-layout-spec.md`）

| 项 | 规格 |
|----|------|
| 纸张/边距 | A4；左右 18mm、上 19mm、下 18mm |
| 正文字体 | 宋体 Songti SC Regular（Songti.ttc face 6）/ Bold（face 1） |
| 正文字号 | **12pt（小四）**，行距 7.2mm，首行缩进 2 字 |
| 配色 | 蓝白：主蓝 `#1D4E7A`、中蓝 `#306FA3`、浅蓝 `#E2ECF6`、细线 `#CBD8E5` |
| 语义色 | 利好 `#B22222` 红、利空 `#007448` 绿（A 股习惯色，不随主题改） |
| 封面 | 白底蓝字，31pt 深蓝主标题 + 目录（真实页码 Pn）+ **居中**免责声明 |
| 章节 | 18.5pt 深蓝 + 左侧竖条 + 浅蓝分隔线，每章新页 |
| 模块一 | 每条自动编号 `1、2、3……`（深蓝加粗序号） |
| 模块三 | 上海/江苏/浙江独立成 15.5pt 深蓝粗体小标题 |
| 模块四 | 大涨股分块：序号 + 股票名 15pt 加粗 + 代码 + 涨幅（红）+ 行情行 + **元数据/判定/事件 三段各起一行** |
| 模块五 | 分组小标题 14pt 深蓝加粗 + 蓝色方块；个股名(代码)加粗 |
| 分页 | 章节自适应压排（0.96→0.80 压行距，字号不变）+ 孤行控制 + 中文禁则 |

### 6.2 渲染器行为（写 markdown 前必读）

- 每个 `##` 独占一页；纯日期型 `##` 与 `# ` H1 被跳过（封面已渲染日期，不会多空白页）
- **`**` 不解析**（原样输出），markdown 里只写纯文本；**emoji 不渲染**，别用
- 表格 `| a | b |` → `列头: 值 | 列头: 值` 结构化文本；`>` 引用块 → 免责声明样式
- 利好/利空自动着色：`（利好：…）` 红、`（利空：…）` 绿（同一括号内 `；利空：…` 分开着色）
- 模块四按 `【元数据】【判定】【事件】` 三段解析；模块五以「：」结尾的短行升级为分组小标题
- 字体缓存：`$BRIEFING_FONT_CACHE` → `~/.cache/a-share-briefing/fonts` → 系统临时目录
  （从 `.ttc` 提取宋体，首次 5-8 秒，各约 20MB，属正常）
- 目录页码由两遍渲染计算；`feat/morx NOT subset` 警告无害

### 6.3 生成后必做自检

```bash
python3 ~/Desktop/TJU/dsh插件/Word文档+PDF实时预览/dsh-doc-preview/tools/pdf_audit.py \
  "$HOME/Desktop/暑假/投资分析/晨间简报/${YYYYMMDD}_A股晨间简报.pdf" --expect-pages <页数>
```

- **fail 必须为 0**（无越界 / 无压叠 / 无缺失字号 / 无 Type3）
- 页数：v2 早报通常 **10-12 页**（12pt 正文的必然结果，比 v1 的 6-8 页多，**不要误判为失败**）
- 抽样比对：股票代码 + 两位小数数值与源 md **零缺失**；行首无标点；目录 Pn 与实际章节页一致
- 交付话术分两段：「已自动校验」与「待人工目视」（蓝色打印深度、白底留白、压排页行距差异）

### 6.4 其他注意事项

- **改渲染脚本必须同步三份副本**：`~/.hermes/scripts/`、`~/.hermes/profiles/stock-analyst/scripts/`、
  本技能 `scripts/`（`collect_stock_meta.py` 同理）。只改一处会让不同入口跑出版式不一致。
- **fpdf2 依赖**：venv 需装 `fpdf2 >= 2.8` 与 `fontTools`（脚本用 fontTools 从 ttc 抽 face）：
  ```bash
  $HOME/.hermes/hermes-agent/venv/bin/pip install fpdf2 fonttools
  ```
- 已交付的旧 PDF 要返工：**用新脚本从 .md 重新生成**，不要用 pikepdf 改页面（页码会错）。

---

## 7. 微信 PDF 发送

```bash
# 带指数退避重试的发送器（推荐；12 次尝试，30s 基数）
$HOME/.hermes/hermes-agent/venv/bin/python3 \
  $HOME/.hermes/scripts/send_wechat_pdf_retry.py \
  "<YOUR_CHAT_ID>@im.wechat" \
  "$HOME/Desktop/${YYYYMMDD}_A股晨间简报.pdf"
```

- **v0.22.5 起微信发送模块搬家**：`send_wechat.py` / `send_wechat_pdf_retry.py` 里的
  `from gateway.platforms.weixin import send_weixin_direct` 会报 `ModuleNotFoundError`，
  必须改成 `from plugins.platforms.weixin.adapter import send_weixin_direct`（函数签名不变，
  仍需在 `~/.hermes/hermes-agent` 目录下、用 venv python 运行）。升级 Hermes 后先跑一次文本探活，
  报这个错就是该改导入，不要误判成 gateway 挂了。
- 简单版：`send_wechat_pdf.py <chat_id> <pdf_path>`（无重试）
- 内部走 iLink Bot API；PDF 走 send_document，图片走 send_image_file
- **限流错误**：`iLink sendmessage rate limited; cooldown active for 30.0s` —
  retry 脚本自动处理；手动处理：等 60s 冷却再发，或
  `kill $(pgrep -f "gateway.*run") 2>/dev/null` 清掉旧 gateway 再发
- **Gateway 冲突**：`Weixin bot token already in use (PID XXXX)` → 同上 kill 后重试
- **`session not ready: ret=-2 ... prepare failed`**（脚本先打印 `session expired for xxx; retrying without
  context_token`）：是 iLink 会话上下文过期，**不是** gateway 挂了。让用户先在微信里给 bot 发任意一条消息，
  再重发即可（同一 chat_id 通常几分钟内就恢复）。早报推送前先用文本探活
  （`send_wechat.py <chat_id> "test"`），文本通了再发 PDF；不要为此反复重启 gateway。
- PDF 发送失败且无法恢复时：把 markdown 内容作为纯文本发微信（比不发强），
  并告知用户 PDF 生成失败

---

## 8. 定时任务（cron）配置

**现行配置：工作日 08:00，一份 job 交付两份报告（早报 + 自选股日报）。**

用 `cronjob_manage action=create` 在**默认 profile** 建 LLM job：
- schedule `0 8 * * 1-5`。周末非交易日不排；用户坚持"每天"再改 `0 8 * * *`，并在 prompt 里明确
  "非交易日最终回复只写一句『今日非交易日，未生成』、不发微信"，否则周末会推一份空报告。
- skills `["a-share-morning-briefing"]`，enabled_toolsets `["web","terminal"]`，workdir 用户主目录。
- deliver `local`：PDF 由 job 内部脚本自己推微信，cron 再投递一次 = 重复轰炸。
- prompt 必须**自包含**（cron 无会话上下文、不能提问），按序写死：确认日期星期 → 一次采集（collect_morning_data.py
  + 涨停池 + fid=f171 涨跌幅榜 + 龙虎榜 + 一条 collect_stock_meta.py 全包）→ 两份 markdown → 两份 PDF 并核页数
  → 先早报、`sleep 40` 再自选股 → 最终回复只给两条绝对路径 + 各一句结论，不复述流程。

**⚠️ 归档技能 cron 加载不到（最容易翻车的一步）**：技能被 curator 归档到 `~/.hermes/skills/.archive/<name>/`
后，`skill_view` 与 cron 的 `skills` 参数都找不到它（报 `Skill '<name>' not found`），job 到点会以"无此技能"空跑。
建 job **前**先确认技能在活目录，不在就整目录（含 references/ 与 scripts/）拷回：

```bash
cp -R ~/.hermes/skills/.archive/a-share-morning-briefing ~/.hermes/skills/finance/
```

**建完立即验证一次**：`cronjob_manage action=run` 触发一次真实运行，并通过 `prompt` 参数补一句
“本次为验证运行，当前实际时间约 X 点，仍按昨日收盘口径生成”——job prompt 里写死的“现在是早上 8:00”
会让盘中运行把盘中价当盘前数据。运行结果异步回来，不要轮询。

⚠️ **验证运行期间不要重启 gateway / 不要改 config**：cron 调度器跑在 gateway 进程内，重启会让这次 run
的终态记账丢失，回报成 `status=error ... whether side effects ran is unknown`（实测 2026-10-28 盘中验证：
回报失败，但两份 PDF 都已生成并 `✅ PDF sent`，job 的 last_status 仍是 ok）。要改配置就等 run 回来再改。

**历史 no_agent 版本（已不用）**：schedule `30 7 * * 1-5` + script=`morning_briefing.sh`，deliver origin，
靠 stdout 为空实现非交易日静默。

**跨 profile 检查**：`cat ~/.hermes/profiles/*/cron/jobs.json`；`cronjob list` 只显示当前 profile。

---

## 9. 故障排查速查表

| 症状 | 根因 | 处理 |
|------|------|------|
| 脚本跑很久没结果（>10min） | perl alarm 失效 + DeepSeek 慢 | kill 进程，换 `morning_briefing_current.sh` 或手动路径 B |
| `ModuleNotFoundError: fpdf` | fpdf2 未装 | venv pip install fpdf2 |
| curl 返回空/exit 52 | 东财 API 限流/封 IP | 按 §3.3 阶梯：重试 → 换主机(push2delay/82.push2) → curl 重取 → 最后才 browser |
| 个股 f2/f3 全是 "-" | 盘前无实时数据 | 用 fid=f171 取昨日涨跌幅 |
| 微信发送 rate limited | iLink 冷却 | retry 脚本自动退避；手动等 60s |
| `session not ready: ret=-2 prepare failed` | iLink 会话上下文过期 | 让用户先给 bot 发一条消息，再重发；先文本探活再发 PDF，别重启 gateway |
| `Weixin bot token already in use` | 多个 gateway 抢占 | kill $(pgrep -f "gateway.*run") |
| 个股分析只有新闻没有基本面 | 没跑元数据采集 | 跑 `~/.hermes/scripts/collect_stock_meta.py <代码...>`，按 §3.7 补【元数据】+【判定】 |
| collect_stock_meta.py 同业对比显示"未获取" | 东财 push2 限流 | 脚本已自动切 push2delay；仍失败就写"同业中位数未获取"并退化为自身历史期对比 |
| DeepSeek API 全挂 | 服务商故障 | 用当前会话模型（方式 C）直接生成 |
| 简报内容空/只有几行 | stock-analyst 模型超时/未响应 | 手动路径 B：自己收数据写简报 |
| 假期后第一天的晨报缺假期新闻 | 模型只写了昨天 | 新闻模块显式要求覆盖整个假期 |
| cron 运行报 `Scheduler restarted after this execution's owner exited before a durable terminal state; whether side effects ran is unknown` | 跑 job 期间重启了 gateway（cron 调度器在 gateway 进程里） | 别在 cron 飞行中重启 gateway。先查 `~/.hermes/cron/output/<job_id>/<日期>_<时刻>.md` 的 Response 段 + `ls` 两份 PDF，若已生成且 Response 里写了 `✅ PDF sent`，就是记账被截断、任务实际成功；`cronjob list` 的 last_status 也常见 ok。**不要再 run 一次**，否则微信重复推送 |

---

## 10. 用户偏好红线（违反=返工，务必逐条遵守）

1. 交付物 = **PDF 文件 + 微信推送**，不是聊天文本
2. **PDF 每个 `## ` 独占一页**；某章零星溢出时优先压行距塞进一页（0.96→0.80），压不进才跨页
3. **PDF 内禁止出现 `**` 残留**；表格渲染为结构化文本而不是被丢弃
4. 新闻模块**每条带板块利好/利空标注**
5. **假期后新闻覆盖整个假期**
6. 省市动态**细化到细分领域+具体公司（名称+代码）**，禁止空泛
7. 大涨股分析**每日精选 5 只**、每只 150 字以上、真实数据；ST / 扣非为负 / 市值过小 / 机构缺位的
   垃圾股剔除，并在「剔除说明」写明理由
8. 今日关注推荐**至少 10 支**，新股申购必须**细分领域+名称+代码+申购日期+发行价**
9. 科创板/创业板半导体等推荐**必须具体代码+名称**，不能只写概念
10. 语气客观中立，**禁止买卖建议**；每只股票名称+6 位代码
11. **个股分析必须来自公司元数据**（2026-09-12 用户要求）：先跑 `scripts/collect_stock_meta.py`（或 `~/.hermes/scripts/` 同名脚本），每支股票带【元数据】段+【判定】；只靠新闻文章归因 = 返工
12. 元数据字段缺失写「未获取」，**绝不编造**；亏损股 PE 写"亏损/不适用"改用 PB/PS；港美股与 A 股币种不同不得混比
13. **PDF 版式走 v2 蓝白**（2026-10-28 用户定）：深红金主题已废弃；正文宋体小四 12pt，**压页只压行距、绝不缩字号**
14. **模块一每条新闻自动编号**（1、2、3……）、**模块三省份名放大加粗**、**模块四大涨股分块**（股票名加黑 +
    元数据 / 判定 / 事件 各起一行）、**模块五分组小标题加粗** —— 这四项是用户逐条提过的，缺一条即返工
15. **大涨股每日精选 5 只**，ST / 扣非为负 / 市值过小 / 机构缺位的垃圾股剔除，并在「剔除说明」写明理由
16. **交付前跑 `pdf_audit.py` 且 fail = 0**；封面目录页码 = 各章实际起始页，页脚总页数 = 实际页数

---

## 11. 相关参考文件

- `references/company-metadata-analysis.md` — **元数据驱动分析的强制规范（2026-09-12 建立）**：字段→分析含义映射、三类判定、个股段输出模板、红线、已知坑
- `scripts/collect_stock_meta.py`（及 `~/.hermes/scripts/` 同名副本）— **公司元数据一次性采集器**：行业/主营/市值/PE/PB/近3期业绩/毛利率ROE负债率/股东户数/机构持仓/公告/同业中位，沪深北通用
- `references/briefing-sources-and-format.md` — 数据源明细 + 通用内容模式（避险模式/芯片股/ETF 放量/假期缺口）
- `references/eastmoney-stock-ranking-api.md` — 东财排序 API 字段详解
- `references/wechat-pdf-delivery.md` — 微信发送细节 + send_weixin_direct API 签名
- `references/pdf-layout-spec.md` — **PDF 版式规范 v2（蓝白，2026-10-28 定稿）**：页面/字体/配色/组件规格/分页规则/自检清单/版面红线，改版式先看它
- `references/watchlist-daily-report.md` — 自选股日报（同 profile 的兄弟任务，勿混淆）
