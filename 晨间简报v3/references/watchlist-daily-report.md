# 自选股日报 (Watchlist Daily Report)

自选股池：招商轮船 601872、南山铝业 600219、紫金矿业 601899、大秦铁路 601006。

**当前有 cron 兜底**：默认 profile 的工作日 08:00 job 一次交付「早报 + 自选股日报」两份（配置与坑见 SKILL.md §8）。
用户单独要求时仍手动生成；`cronjob list` 只显示当前 profile，跨 profile 查 `~/.hermes/profiles/*/cron/jobs.json`。

## 生成流程（5 步）

1. `date '+%Y-%m-%d %A %H:%M'` + `ls ~/Desktop/暑假/投资分析/自选股日报/`：确认交易日、确认当日 PDF 是否已存在。
   当日已生成且已推送 → 先问用户再决定是否重发（微信重复轰炸比晚发更烦）；日期已变 → 按新日期全流程重做，不复用上次的"昨日"数字。
2. 一次采集（可在同一条 terminal 调用里并行）：
   - `python3 ~/.hermes/profiles/stock-analyst/scripts/collect_stock_watch.py` — QUOTES / KLINE / ANNOUNCEMENTS / INDUSTRY NEWS / POLICY NEWS
   - `collect_stock_meta.py 601872 600219 601899 601006 --json /tmp/meta_$(date +%Y%m%d).json` — 元数据（模块一估值对标、模块五股息率与筹码都要用）
3. 写 markdown：首行 `# 【自选股日报】YYYY年M月D日（星期X）`，`##` 章节 / `###` 子标题 / `-` 列表 / `|` 表格 → `/tmp/daily_report_YYYYMMDD.md`。派生指标（溢价倍数、股息率）在生成脚本里算好再套进文本，不手算。
4. `python3 scripts/gen_daily_stock_report.py /tmp/daily_report_YYYYMMDD.md ~/Desktop/暑假/投资分析/自选股日报/自选股日报_YYYYMMDD.pdf`
   （紧凑封面版式，**不要**用早报的 gen_briefing_pdf_v2.py —— 两者版式定位不同）。校验：3-4 页、>150KB。
5. 发微信：`~/.hermes/hermes-agent/venv/bin/python3 scripts/send_wechat_pdf_retry.py <YOUR_CHAT_ID>@im.wechat <pdf>`；
   与早报同日推送时隔 ≥35s（iLink 30s 冷却是全局的），看到 `✅ PDF sent` 才算完成。

## 六模块结构

一、今日行情总览 — QUOTES 表（收盘价/涨跌幅/振幅/换手/PE/PB/总市值）+ 近5日走势 + 估值与同业对标表
二、每日新动向 — 逐股 `###`，只写近 1-2 日**新增**公告/事件（日期+标题+内容+解读）；确实没有就写"近两日无新增公告"并附最近一条
三、重点时政要点 — 每条带影响标注（利好/利空/中性）
四、行业与市场动态 — 航运/有色/煤炭铁路各一条，把行业事件挂到公司中报数据上（营收净利同比、毛利率、ROE）
五、资金与估值提示 — PE/PB/负债率/分红与股息率表 + 筹码与机构持仓 + 风险提示
六、明日关注要点 — 逐股 1-2 个跟踪点 + 免责声明

## 数据口径（写错会被退回）

- **涨跌幅用 KLINE 最近两个交易日收盘价核算**：盘前腾讯 quotes 的"昨收"字段会滞后（返回的是前一个交易日收盘），
  "现价"其实是最近一个收盘价，直接用 quotes 的涨跌幅字段核对即可，不要用"现价 vs 昨收"自行相除。
- **PE/PB 用 quotes 的 TTM 口径**；同业对标用 `collect_stock_meta.py` 的同业中位输出，缺失写"未获取"并说明原因，不估算替代。
- **股息率用 F10 分红接口实算，不要引用新闻里的数字**：
  `datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_SHAREBONUS_DET&columns=ALL&filter=(SECUCODE="601872.SH")&sortTypes=-1&sortColumns=REPORT_DATE`
  （`PRETAX_BONUS_RMB`=每10股税前派息元；`REPORT_DATE` 的月份决定性质：06-30=中期分配、12-31=年报分配；
  `ASSIGN_PROGRESS`=预披露/董事会决议通过/股东大会决议通过/实施分配；`EX_DIVIDEND_DATE`=除权日）。
  必须给两个口径并标明：①「近12个月已实施分红」——按除权日落在近 12 个月内的方案加总；②「本年度中期方案」——未除权的单列并注明尚未除权。
- 分红一律写「每10股派 X 元（税前）」，不要改写成每股口径。
- 中期方案容易被误当年报：判断性质只看 `REPORT_DATE`（06-30 vs 12-31），不要按年份猜。

## 格式与红线

- 客观中立、禁止买卖建议；每股 名称+6位代码；数据必须来自采集脚本与 F10，禁止编造，缺失写"未获取"。
- 只用 terminal/API 采集，不用浏览器（自动任务里浏览器会挂到超时）。
- 页数 3-4 页为准（历史 180-270KB）。
