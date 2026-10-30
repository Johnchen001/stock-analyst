# East Money Stock Ranking API (东方财富行情排名API)

## Overview

For pre-market morning briefings (~07:30-08:00 Beijing time), real-time endpoints return "-" for price/change fields because no trading has occurred yet. **You must use the historical-compatible `f171` field** to get yesterday's change %.

## Core Endpoint

```bash
# Stock listing with ranking
https://push2.eastmoney.com/api/qt/clist/get
```

### Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `pn` | 1 | Page number |
| `pz` | 10 | Page size (items per page) |
| `po` | 1 | Sort order: 1=descending, 0=ascending |
| `np` | 1 | No-paging flag (usually 1) |
| `fltt` | 2 | Float type (usually 2) |
| `invt` | 2 | Investment type (usually 2) |
| `fid` | f171 | **Sort field** — use `f171` for yesterday's change % |
| `fs` | m:0+t:6,m:1+t:2,m:1+t:23 | Market filter (see below) |
| `fields` | f12,f14,f2,f3,f18,f170,f171 | Fields to return |
| `ut` | bd1d9ddb04089700cf9c27f6f7426281 | Auth token (constant) |

### Market Filter (`fs`) Values

| Value | Market |
|-------|--------|
| `m:0+t:6,m:1+t:2,m:1+t:23` | **All A-shares** (SH+主板+创业板) — most common |
| `m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23` | All A-shares **including B-shares** |
| `m:0+t:6` | Shanghai A-shares only |
| `m:1+t:2` | Shenzhen main board only |
| `m:1+t:23` | ChiNext (创业板) only |
| `m:0+t:80` | Shanghai B-shares |

### Field Definitions

| Field | Meaning | Notes |
|-------|---------|-------|
| `f12` | Stock code | e.g. "600000" |
| `f14` | Stock name | e.g. "浦发银行" |
| `f2` | Latest price | **Returns "-" before market open** |
| `f3` | Today's change % | **Returns "-" before market open** |
| `f4` | Today's change amount | **Returns "-" before market open** |
| `f15` | Today's high | **Returns "-" before market open** |
| `f16` | Today's low | **Returns "-" before market open** |
| `f17` | Today's open | **Returns "-" before market open** |
| `f18` | **Yesterday's close** (昨收) | Always available — yesterday's closing price |
| `f170` | **Yesterday's change amount** (涨跌额) | Works before market open! |
| `f171` | **Yesterday's change %** (涨跌幅%) | **KEY FIELD — use as sort target!** |
| `f100` | Industry sector | e.g. "半导体" |

### ⚠️ Critical: Pre-Market Sorting

**Do NOT sort by `f3`** when the market hasn't opened. Since f3 returns "-" for all stocks, the API falls back to a default sort (usually by code), producing the wrong ranking.

**Always sort by `fid=f171`** to get yesterday's top gainers:

```bash
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f171&fs=m:0+t:6,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f18,f170,f171"
```

### Example: Top 10 Gainers (Yesterday)

```bash
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f171&fs=m:0+t:6,m:1+t:2,m:1+t:23&fields=f12,f14,f18,f170,f171" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if d.get('data') and d['data'].get('diff'):
    items=d['data']['diff']
    for i,item in enumerate(items,1):
        print(f\"{i}. {item.get('f12','')} {item.get('f14','')} 昨收={item.get('f18')} 涨跌幅={item.get('f171')}%\")
"
```

### Example: Top 10 Losers (Yesterday)

Change `po=1` to `po=0` (ascending):

```bash
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=0&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f171&fs=m:0+t:6,m:1+t:2,m:1+t:23&fields=f12,f14,f18,f170,f171"
```

---

## 龙虎榜 (Dragon-Tiger Board) Data

### Method 1: Web Page (most reliable)

Navigate to the East Money 数据中心 page:

```
https://data.eastmoney.com/stock/tradedetail.html
```

This loads with **today's date** by default. The page already shows data for the selected date.
- The "数据日期" selector shows the current date (e.g. "2026-07-28")
- The table includes: 代码, 名称, 收盘价, 涨跌幅, 龙虎榜净买额, 买入额, 卖出额, 换手率, 上榜原因
- Use `browser_console` with JS to extract the full table programmatically

**JS extraction snippet** (run in browser_console):
```javascript
(() => {
  const rows = document.querySelectorAll('table tr');
  const result = [];
  rows.forEach((row) => {
    const cells = row.querySelectorAll('td');
    if (cells.length >= 17) {
      result.push({
        seq: cells[0]?.textContent?.trim(),
        code: cells[1]?.textContent?.trim(),
        name: cells[2]?.textContent?.trim(),
        close: cells[5]?.textContent?.trim(),
        change: cells[6]?.textContent?.trim(),
        netBuy: cells[7]?.textContent?.trim(),
        buyAmt: cells[8]?.textContent?.trim(),
        sellAmt: cells[9]?.textContent?.trim(),
        reason: cells[16]?.textContent?.trim()
      });
    }
  });
  return JSON.stringify(result, null, 2);
})()
```

### Method 2: API (programmatic)

The 龙虎榜 data is loaded from a datacenter API endpoint. The exact URL can be found by inspecting the network requests on the page above. Fall back to the web page method if the API isn't immediately identified.

### Key Data Fields (from the table)

| Column | Meaning |
|--------|---------|
| 收盘价 | Closing price |
| 涨跌幅 | Change % (can be positive or negative) |
| 龙虎榜净买额(万) | Net buy amount from dragon-tiger seats (in 10k CNY) |
| 龙虎榜买入额(万) | Total buy amount (in 10k CNY) |
| 龙虎榜卖出额(万) | Total sell amount (in 10k CNY) |
| 换手率 | Turnover rate |
| 上榜原因 | Reason for listing (e.g. "日涨幅偏离值达到7%的前5只证券") |

### Common 上榜原因 (Listing Reasons)

| Reason (Chinese) | Meaning |
|------------------|---------|
| 日涨幅偏离值达到7%的前5只证券 | Daily price deviation ≥7% |
| 连续三个交易日内涨幅偏离值累计达到20% | 3-day cumulative deviation ≥20% |
| 日换手率达到20%的前5只证券 | Daily turnover rate ≥20% |
| 日跌幅达到15%的前5只证券 | Daily drop ≥15% (ChiNext/STAR) |
| 日涨幅达到15%的前5只证券 | Daily gain ≥15% (ChiNext/STAR) |
| 日振幅值达到15%的前5只证券 | Daily amplitude ≥15% |
| 日换手率达到30%的前5只证券 | Daily turnover ≥30% (ChiNext/STAR) |
| 有价格涨跌幅限制的日收盘价格涨幅偏离值达到7% | Same as 日涨幅偏离值达到7% (SH main board) |

---

## Combining Both in a Briefing

For a morning briefing:

1. **Get yesterday's top gainers** via `fid=f171` sort on the clist API
2. **Get 龙虎榜 data** from the data.eastmoney.com web page
3. Cross-reference: the 龙虎榜 will include stocks with >7% or >15% gains (only those that triggered the rule), while the f171 sort gives the complete ranking
4. Note that 科创板 stocks (688xxx) can have higher daily limits (up to 20%), so the top 10 gainers are often dominated by 科创板 stocks

---

## 个股元数据接口 `stock/get`（行业/估值/最新财务比率，一次取全）

```
https://push2.eastmoney.com/api/qt/stock/get?invt=2&fltt=2&fields=f57,f58,f84,f85,f105,f116,f117,f127,f128,f162,f167,f173,f183,f184,f185,f186,f187&secid=1.600584
```
secid 规则：沪市 `1.600584`、深市 `0.000001`、北交所 `0.920212`（92/43/83/87/88 开头的代码一律 market=0）。

| 字段 | 含义 |
|------|------|
| f57 / f58 | 代码 / 名称 |
| f84 / f85 | 总股本 / 流通股 |
| f105 | 归母净利（元） |
| f116 / f117 | 总市值 / 流通市值（元） |
| f127 | **东财行业名**（如「半导体」）——比 F10 的 EM2016 细分名更适合匹配行业板块 |
| f128 | 地域板块（如「江苏板块」） |
| f162 / f167 | PE(动) / PB |
| f173 | ROE（最新报告期） |
| f183 / f184 | 营收（元）/ 营收同比% |
| f185 | 归母净利同比% |
| f186 / f187 | 毛利率% / 净利率% |

对照：腾讯 `qt.gtimg.cn`（GBK 解码）给 **PE(TTM)** 与现价，`f[38]`换手 `f[39]`PE(TTM) `f[44]`流通市值(亿) `f[45]`总市值(亿) `f[46]`PB；两者一起用（腾讯 PE(TTM) + 东财 PE(动)/行业/ROE）。

## 板块接口（同业可比公司的来源）

```
# 个股所属板块（slist）：拿到该股的全部概念/行业/地域板块
https://push2.eastmoney.com/api/qt/slist/get?spt=3&fltt=2&invt=2&fields=f12,f13,f14&secid=1.600584&pi=0&pz=40&po=1&fid=f3
# 行业板块名录（含 BK 码）
https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f12,f14
# 板块成分（按总市值排序）
https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=1&np=1&fltt=2&invt=2&fid=f20&fs=b:BK1036&fields=f12,f14,f2,f9,f23,f20
```

- **`slist` 的 `data.diff` 是 dict（`{"0":{...}}`），`clist` 是 list** —— 解析前先归一化，否则 `diff[:12]` 报 `unhashable type: 'slice'`。
- **行业板块名录单页最多 100 条（total≈496）**：必须 `pn=1..6&pz=100` 翻页。只取第一页会漏掉「半导体」「航运」等细分板块，同业对比就会被迫退到过宽的「电子」板块。
- 找个股的行业板块：`slist` 命中的板块 ∩ 行业板块名录的 BK 值，再用行业名打分挑最贴切的那个（slist 里概念/风格板块很多，「毫米波概念」「科技风格」这类要排除）。
- 同业中位数按板块前 N 大市值算，**小市值股会被巨头带偏**：同时给「市值相近可比公司(0.3~3 倍)」，板块内确实没有相近体量就如实说明，不硬凑。

## F10 datacenter 报表速查（估值报告与元数据的财务来源）

```
https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName={REPORT}&columns=ALL
  &filter=(SECUCODE%3D%22600584.SH%22)&pageNumber=1&pageSize=3&source=HSF10&client=PC
  &sortTypes=-1&sortColumns=REPORT_DATE
```
金额单位是「元」（转亿元除 1e8）；SECUCODE 要带交易所后缀（`600584.SH` / `000001.SZ` / `920212.BJ`）。

| 报表 | 排序列 | 关键字段 |
|------|--------|---------|
| `RPT_F10_BASIC_ORGINFO` 公司概况 | **无排序列** —— 带 `sortTypes/sortColumns` 直接 `code 9501 排序列不存在`、result=null | ORG_NAME / EM2016（行业三层）/ INDUSTRYCSRC1 / PROVINCE / LISTING_DATE / EMP_NUM / ACTUAL_HOLDER / CHAIRMAN / MAIN_BUSINESS / ORG_PROFILE |
| `RPT_F10_FINANCE_GINCOME` 利润表 | REPORT_DATE | TOTAL_OPERATE_INCOME(+_YOY) / PARENT_NETPROFIT(+_YOY) / DEDUCT_PARENT_NETPROFIT / RESEARCH_EXPENSE |
| `RPT_F10_FINANCE_MAINFINADATA` 主要指标 | REPORT_DATE | **营收/净利字段恒为 None** → 只取 XSMLL 毛利率 / XSJLL 净利率 / ROEJQ ROE / ZCFZL 资产负债率 / LD 流动比 / SD 速动比 / MGJYXJJE 每股经营现金流 / EPSJB / BPS |
| `RPT_F10_EH_HOLDERNUM` 股东户数 | **END_DATE**（用 REPORT_DATE 会 9501） | HOLDER_TOTAL_NUM / TOTAL_NUM_RATIO(环比%) / AVG_FREE_SHARES / HOLD_FOCUS(集中度) |
| `RPT_F10_EH_FREEHOLDERS` 十大流通股东 | **END_DATE** | HOLDER_NAME / FREE_HOLDNUM_RATIO / IS_HOLDORG(是否机构) / HOLDER_TYPE / HOLD_NUM_CHANGE |

公告列表（拿回购/扩产/增发/激励等最新事件，比新闻转述硬）：
```
https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=6&page_index=1&ann_type=A&client_source=web&stock_list=600584
```

现成实现：`scripts/collect_stock_meta.py` 已封装以上全部（腾讯行情 + F10 + 公告 + push2/push2delay 多主机容灾 + curl 回退 + 6 线程并发），直接调用，不要重写。
