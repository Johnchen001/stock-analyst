# A-Share Morning Briefing — Data Sources & Format Reference

## Confirmed Working Data Sources (2026-07)

| Source | URL | Data Collected |
|--------|-----|---------------|
| **新浪财经 7x24小时直播** | https://finance.sina.com.cn/7x24/ | **首选新闻来源** — 实时财经新闻流，按时间倒序排列，一次加载即可获取大量新闻。点击底部"A股"标签可筛选A股新闻，15:00附近有收评总结、09:25有开盘综述。比东方财富更易获取精炼新闻，无需滚动大量无关内容 |
| 东方财富 财经首页 | https://finance.eastmoney.com/ | Headline news, index data, calendar, fund flows, expert commentary |
| 东方财富 证券聚焦 | https://finance.eastmoney.com/a/czqyw.html | Curated latest news list with summaries + timestamps; 网友点击排行榜 for trending topics |
| 东方财富 push2 API | `https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14&secids=<secids>` | Real-time A-share index data (f2=price, f3=change%, f4=change, f12=code, f14=name). Use secids=1.000001,0.399001,0.399006,1.000688 for major indices |
| 东方财富 push2 US API | `https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14&secids=100.NDX,100.DJI,100.SPX` | US market index data (NDX=纳斯达克, DJI=道琼斯, SPX=标普500). Returns f2=price, f3=change% |
| 东方财富 行情中心 (gridlist) | `https://quote.eastmoney.com/center/gridlist.html#hs_a_board` | Live stock ranking table sorted by 涨跌幅 (fallback when push2 API fails); shows global indices in top bar |
| 东方财富 新股数据 | https://data.eastmoney.com/xg/ | IPO calendar: upcoming 申购 dates, 中签缴款 due dates, 上市 dates, 发行价, 市盈率 |

## Briefing Output Format

当前版式（v2 蓝白）的完整规格在 **`references/pdf-layout-spec.md`**，此处只列结构骨架，
不要按旧的四模块/emoji 版式写（那是 v1 早期形态，已废弃）：

```markdown
# A股晨间简报
## YYYY年M月D日 周X          ← 日期行，渲染器会跳过（封面已渲染）

## 一、隔夜市场与重大新闻      ← 每条段落末尾写（利好：板块）/（利空：板块），编号由渲染器生成
## 二、昨日（M月D日）A股收盘回顾
## 三、省市投资动态（江浙沪）   ← 每段以「上海：」「江苏：」「浙江：」开头，渲染成省份小标题
## 四、昨日（M月D日）大涨股分析 ← 每只：名称(代码)，板块，昨日涨X%收Y元。【元数据】…【判定】…【事件】…
                               ← 每日精选 5 只，垃圾股剔除并写「剔除说明」
## 五、今日（M月D日）关注与推荐 ← 分组标题独立成行、以「：」结尾（新股申购：/ 上涨潜力股：…）

> 免责声明：…（渲染为 9.5pt 灰，段前分隔线）
```

## Key Market Data Points (check these specifically)

### Indices to report
- 上证指数 (SH000001)
- 深证成指 (SZ399001)
- 创业板指 (SZ399006)
- 北证50 (BI50)
- 恒生指数 (HSI)
- 纳斯达克 (IXIC) / 道琼斯 (DJI)
- 日经225 / 韩国KOSPI / 台湾加权

### Capital Flow Top Stocks (from 同花顺)
Check the "资金流向" table on 同花顺 for the top inflows by stock (net amount in 亿).

### Dragon-Tiger List (龙虎榜)
Available on both eastmoney and 同花顺. Shows stocks that hit daily gain limits with anomaly reasons.

### IPO Calendar (新股日历)
Check for:
- 今日申购 (today's subscription)
- 今日中签缴款 (lottery payment due today)
- 即将上市 (upcoming listing dates)

## Common Content Patterns

### When market is down (避险模式)
- Highlight defensive sectors: 银行, 白酒, 电力, 高股息
- Note capital flowing into: 工商银行, 贵州茅台, 长江电力, 农业银行

### When US chip stocks crash
- A-shares 半导体/芯片 sector likely follows down
- But domestic substitution themes (国产替代) may benefit: 中微公司, 北方华创, 中芯国际
- 液冷服务器, 网络安全 concepts often counter-trend

### When ETF volumes surge abnormally (单日成交破百亿)
- Massive ETF volume (e.g., 创业板ETF易方达, 科创50ETF华夏 >100亿) signals institutional bottom-fishing / government-backed stabilization
- Often precedes a short-term bounce in the corresponding index
- Note the specific ETF name and volume in the briefing news section
- Check whether ETF net subscription data is available (e.g., 东财 "ETF追踪" articles)

### Weekend/holiday gap
- First trading day after a break must cover ALL days of the break
- Check for accumulated news during the gap period
