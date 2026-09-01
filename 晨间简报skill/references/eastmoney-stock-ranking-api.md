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
