# 自选股日报 (Watchlist Daily Report) — stock-analyst profile

Sibling cron job to the morning briefing. Lives in the **stock-analyst** profile, NOT the default profile — invisible to the current session's `cronjob list`.

## Job facts

| Item | Value |
|------|-------|
| Job ID | `164824b0072f` |
| Profile | `stock-analyst` (`~/.hermes/profiles/stock-analyst/cron/jobs.json`) |
| Schedule | `0 8 * * 1-5` (workdays 08:00, after the 07:30 morning briefing) |
| Deliver | `weixin:o9cq800hCSIovrI8HvOMYOQ-QHAY@im.wechat` (PDF via MEDIA) |
| Stocks | 招商轮船 601872, 南山铝业 600219, 紫金矿业 601899, 大秦铁路 601006 |
| Created | 2026-08-05 (completed ~3 runs as of 2026-08-09) |

## Pipeline (LLM job, no_agent=false)

1. `python3 scripts/collect_stock_watch.py` (in stock-analyst profile dir, timeout=60) — one step does trading-day check + data collection. Prints `DATA_TIMESTAMP`, then sections:
   - `QUOTES` — 4 stocks: 现价/涨跌/振幅/换手/PE/PB/市值
   - `KLINE` — 近6日收盘价
   - `ANNOUNCEMENTS` — 最近公告 (日期+标题)
   - `INDUSTRY NEWS` — 航运/有色/煤炭等行业新闻
   - `POLICY NEWS` — 时政/政策要点
2. If `DATA_TIMESTAMP` weekday >= 5 or holiday → output `【跳过】今日非交易日` and stop. No PDF, no delivery.
3. Else write markdown to `/tmp/daily_report.md` — first line `# 【自选股日报】XXXX年X月X日（星期X）`, sections `##`, subtitles `###`, lists `-`, tables `|`.
4. `python3 scripts/gen_daily_stock_report.py /tmp/daily_report.md /tmp/daily_report.pdf` — **fixed compact-cover format, NOT gen_briefing_pdf.py** (that one is for the morning briefing's one-section-per-page layout).
5. Copy to `~/Desktop/暑假/投资分析/自选股日报/自选股日报_$(date +%Y%m%d).pdf`
6. Final response ends with `MEDIA:/tmp/daily_report.pdf` → cron delivers PDF to WeChat.

## Report structure (6 sections)

一、今日行情总览 (QUOTES table + 近5日走势 KLINE table)
二、每日新动向 — per-stock 近1-2日新增公告/事件 (日期+标题+核心内容+解读, each 据公司公告/据XX; write "今日无新增公告" if none)
三、重点时政要点 — POLICY NEWS, each with 来源(据XX) + 影响(利好XX/利空XX/中性)
四、行业与市场动态 — INDUSTRY NEWS, each with 来源 + 利好方向
五、资金与估值提示 — PE/PB/股息率估算/估值水平 table + 风险提示
六、今日关注要点 — per-stock 1-2 关注点 + 免责声明

## Rules embedded in the prompt

- 客观中立, no 买卖建议; every stock 名称+6位代码; data must come from script output, 禁止编造
- 严禁浏览器工具, terminal only
- 每日新动向 and 时政要点 modules must be 充实 (don't drop important script news)

## Health-check pattern (from 2026-08-09 audit)

- Output records: `~/.hermes/profiles/stock-analyst/cron/output/164824b0072f/*.md` (each run's Prompt+Response captured)
- Success = PDF exists in `~/Desktop/暑假/投资分析/自选股日报/` AND delivery has no `last_delivery_error`
- Healthy example run: 2026-08-09 20:26 → correctly detected Sunday, output `【跳过】今日非交易日`, no delivery error. This is the expected weekend behavior — a "skipped" output file is normal, not a failure.
- 08-06/08-07 runs produced PDFs (~150-165 KB each), delivery clean — this job was the healthiest of the three finance crons in the audit (morning briefing and 吃药提醒 both showed iLink rate-limit delivery errors).
