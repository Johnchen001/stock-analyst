#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_stock_meta.py — 个股「公司元数据」一次性采集器（晨报/日报/推荐股的强制数据源）

用途：任何个股分析（昨日大涨股、今日关注推荐、自选股日报、估值报告）必须先跑本脚本，
      把公司的行业属性 + 估值 + 财务 + 股东 + 公告 + 同业对比 一次取全；
      分析结论必须从这些元数据推导，新闻只作催化剂标注。

用法：
  python3 collect_stock_meta.py 600584 002371 920212
  python3 collect_stock_meta.py --codes 600584,002371
  python3 collect_stock_meta.py --file /tmp/codes.txt          # 每行一个代码
  cat codes.txt | python3 collect_stock_meta.py                # stdin
  python3 collect_stock_meta.py --json /tmp/meta.json 600584     # 同时落 JSON（供程序化核对）
  python3 collect_stock_meta.py --no-push2 600584               # 跳过低稳定度的 push2 增强源

数据源分层（优先级高→低，高优先级失败自动降级，绝不编造，缺失输出「未获取」）：
  A. 腾讯 qt.gtimg.cn            行情：现价/涨跌/换手/振幅/PE(TTM)/PB/总市值/流通市值  —— 最稳
  B. 东财 F10 datacenter         公司概况 ORGINFO（行业/主营/省份/上市/员工/实控人）
                                 利润表 GINCOME（营收·净利·扣非·研发 + 同比，近3期）
                                 主要指标 MAINFINADATA（毛利率/净利率/ROE/负债率/流动比/每股经营现金流）
                                 股东户数 HOLDERNUM（筹码集中度）· 十大流通股东 FREEHOLDERS（机构动向）
  C. 东财公告 API                最近公告标题（扩产/回购/增发/业绩，逻辑最硬的基本面信号）
  D. 东财 push2 stock/get        行业名(f127)/概念地域板块(f128)/PE动(f162)/ROE(f173) —— 限流频繁，仅作增强
  E. 东财 push2 板块列表+成分     同业可比公司 PE/PB 中位数（估值相对位置）

已知坑（勿再踩）：
  - MAINFINADATA 的营收/净利字段恒为 None → 营收净利用 GINCOME，MAINFINADATA 只补比率
  - ORGINFO 无 REPORT_DATE 排序列 → 调它必须省略 sortTypes/sortColumns，否则 code 9501
  - push2 的 diff 有时是 dict（{"0":{...}}）而非 list → 已统一归一化
  - 腾讯字段索引易偏一位：f[38]换手 f[39]PE(TTM) f[45]总市值(亿) f[46]PB（写死在脚本里，勿手改）
  - 北交所代码（92/43/83/87/88 开头）secid 用 0.xxxxxx、腾讯前缀 bj，不是 sh
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Referer": "https://emweb.securities.eastmoney.com/",
}
TIMEOUT = 12
EM_BASE = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
BJ_PREFIXES = ("92", "43", "83", "87", "88", "82")

_board_cache = {}
_http_stats = {"urllib": 0, "curl": 0, "fail": 0}


# ---------------------------------------------------------------- http 层

def _curl(url, enc):
    """curl 回退：实测东财/腾讯在 urllib 被拒时 curl 常能通（且快得多）"""
    try:
        out = subprocess.run(
            ["curl", "-s", "-m", str(TIMEOUT + 3), "-A", UA["User-Agent"],
             "-H", "Referer: " + UA["Referer"], url],
            capture_output=True, timeout=TIMEOUT + 8).stdout
        _http_stats["curl"] += 1
        return out.decode(enc, "replace")
    except Exception:
        return None


def http_text(url, enc="utf-8", retries=2):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            txt = urllib.request.urlopen(req, timeout=TIMEOUT).read().decode(enc, "replace")
            if txt and txt.strip():
                _http_stats["urllib"] += 1
                return txt
        except Exception:
            pass
        txt = _curl(url, enc)
        if txt and txt.strip():
            return txt
        time.sleep(0.6 * (i + 1))
    _http_stats["fail"] += 1
    return None


def http_json(url, enc="utf-8"):
    txt = http_text(url, enc)
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        # jsonp / 前后缀容错
        s, e = txt.find("{"), txt.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(txt[s:e + 1])
            except Exception:
                return {}
    return {}


def diff_list(d):
    """push2 的 diff 可能是 list 或 dict（键为 '0','1'…），统一成 list"""
    diff = (d.get("data") or {}).get("diff")
    if isinstance(diff, dict):
        return [diff[k] for k in sorted(diff, key=lambda x: int(x) if str(x).isdigit() else 0)]
    return diff or []


PUSH_HOSTS = ["push2", "push2delay", "82.push2"]   # push2 限流时 push2delay 仍可用（延时行情，估值对比足够）
_good_host = []


def push2_json(qs, retries=1):
    """push2 系列接口多主机容灾：push2 → push2delay → 82.push2，命中主机下次优先"""
    for host in _good_host + [h for h in PUSH_HOSTS if h not in _good_host]:
        txt = http_text("https://%s.eastmoney.com/api/qt/%s" % (host, qs), retries=retries)
        if not txt:
            continue
        try:
            d = json.loads(txt)
        except Exception:
            continue
        if d.get("data"):
            if host not in _good_host:
                _good_host.insert(0, host)
            return d
    return {}


# ---------------------------------------------------------------- 工具

def market_of(code):
    """→ (secid, 腾讯前缀, secucode 后缀)"""
    if code.startswith(BJ_PREFIXES):
        return "0." + code, "bj", "BJ"          # 北交所
    if code[:1] in ("6", "9"):
        return "1." + code, "sh", "SH"
    return "0." + code, "sz", "SZ"


def yi(v):
    try:
        return round(float(v) / 1e8, 2)
    except (TypeError, ValueError):
        return None


def num(v, digits=2):
    try:
        f = float(v)
        return round(f, digits)
    except (TypeError, ValueError):
        return None


def nz(v, suffix="", dash="未获取"):
    return dash if v is None else "%s%s" % (v, suffix)


def f10(report, secucode, size=2, sort_col="REPORT_DATE"):
    """sort_col=None 表示该报表无排序列（ORGINFO）；股东类报表要用 END_DATE"""
    u = (EM_BASE + "?reportName=" + report + "&columns=ALL&filter="
         + urllib.parse.quote('(SECUCODE="%s")' % secucode)
         + "&pageNumber=1&pageSize=%d&source=HSF10&client=PC" % size)
    if sort_col:
        u += "&sortTypes=-1&sortColumns=" + sort_col
    return (http_json(u).get("result") or {}).get("data") or []


def tencent_quotes(codes):
    """批量行情：一次调用取全部代码（最稳的估值/行情源）"""
    out = {}
    if not codes:
        return out
    qs = ",".join(market_of(c)[1] + c for c in codes)
    raw = http_text("https://qt.gtimg.cn/q=" + qs, enc="gbk")
    if not raw:
        return out
    for line in raw.strip().split("\n"):
        if "=" not in line:
            continue
        try:
            f = line.split('"')[1].split("~")
            out[f[2]] = {
                "name": f[1], "price": num(f[3]), "prev_close": num(f[4]),
                "chg_pct": num(f[32]), "turnover_pct": num(f[38]), "pe_ttm": num(f[39]),
                "amplitude_pct": num(f[43]), "float_mktcap_yi": num(f[44]),
                "total_mktcap_yi": num(f[45]), "pb": num(f[46]),
            }
        except Exception:
            continue
    return out


ALIAS = {"集成电路": "半导体", "半导体材料": "半导体", "半导体设备": "半导体",
         "消费电子": "消费电子", "光学光电子": "光学光电子"}
_BOARD_CACHE_FILE = os.path.expanduser("~/.hermes/cache/em_sector_boards.json")


def board_list():
    """行业板块名 → BK 码（东财 m:90 t:2 名录，带磁盘缓存 7 天，避免限流时空手）"""
    global _board_cache
    if _board_cache:
        return _board_cache
    try:
        if os.path.exists(_BOARD_CACHE_FILE) and time.time() - os.path.getmtime(_BOARD_CACHE_FILE) < 7 * 86400:
            with open(_BOARD_CACHE_FILE) as f:
                _board_cache = json.load(f)
            if _board_cache:
                return _board_cache
    except Exception:
        pass
    rows = []
    for pn in range(1, 7):        # 该接口单页最多返回 100 条（total≈496），必须翻页
        part = diff_list(push2_json(
            "clist/get?pn=%d&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f12,f14" % pn))
        if not part:
            break
        rows += part
        if len(part) < 100:
            break
    try:
        _board_cache = {str(x.get("f14")): str(x.get("f12")) for x in rows if x.get("f14")}
        if _board_cache:
            os.makedirs(os.path.dirname(_BOARD_CACHE_FILE), exist_ok=True)
            with open(_BOARD_CACHE_FILE, "w") as f:
                json.dump(_board_cache, f, ensure_ascii=False)
    except Exception:
        _board_cache = {}
    return _board_cache


def sector_board_of(secid, industry=None, em_industry=None):
    """反查该股的行业板块 BK 码：slist 命中的板块 ∩ 行业板块名录，再按行业名打分挑最贴切的"""
    try:
        u = ("slist/get?spt=3&fltt=2&invt=2&fields=f12,f13,f14&secid=%s&pi=0&pz=40&po=1&fid=f3" % secid)
        rows = diff_list(push2_json(u))
        if not rows:
            rows = diff_list(push2_json(u))       # 限流时重试一次
    except Exception:
        return None
    names = board_list()
    industry_bks = set(names.values())
    cands = [(str(r.get("f12")), str(r.get("f14"))) for r in rows
             if str(r.get("f12")) in industry_bks]
    if not cands:
        return None
    segs = [s for s in (em_industry or "").split("-") if s]
    if industry:
        segs.append(industry)
    best, best_score = None, -1
    for bk, nm in cands:
        s = 0
        if industry and nm == industry:
            s = 10
        elif any(nm == x for x in segs):
            s = 8
        elif any(nm and x and (nm in x or x in nm) for x in segs):
            s = 4
        if s > best_score:
            best, best_score = (bk, nm), s
    return best if best_score > 0 else cands[0]


def peers_comparison(industry, top_n=10, secid=None, mktcap_yi=None, em_industry=None):
    """同业可比公司 PE(TTM)/PB 中位数（估值相对位置）"""
    bk = None
    board_name = None
    if secid:
        hit = sector_board_of(secid, industry=industry, em_industry=em_industry)
        if hit:
            bk, board_name = hit
    if not bk and industry:
        name = ALIAS.get(industry, industry)
        bk = board_list().get(name)
        if not bk:
            for k, v in board_list().items():
                if name and (name in k or k in name):
                    bk, board_name = v, k
                    break
        else:
            board_name = name
    if not bk:
        return {"board": None, "industry": industry, "samples": [],
                "pe_median": None, "pb_median": None, "pe_n": 0, "pb_n": 0,
                "note": "行业板块未识别（push2 限流或行业名不在名录），同业中位数未获取"}
    u = ("clist/get?pn=1&pz=%d&po=1&np=1&fltt=2&invt=2&fid=f20&fs=b:%s&fields=f12,f14,f2,f9,f23,f20"
         % (top_n, bk))
    rows = diff_list(push2_json(u))
    if not rows:
        return {"board": bk, "industry": board_name or industry, "samples": [], "pe_median": None,
                "pb_median": None, "pe_n": 0, "pb_n": 0, "note": "行业成分拉取失败"}
    pes = [r["f9"] for r in rows if isinstance(r.get("f9"), (int, float)) and r["f9"] > 0]
    pbs = [r["f23"] for r in rows if isinstance(r.get("f23"), (int, float)) and r["f23"] > 0]
    samples = [{"code": r.get("f12"), "name": r.get("f14"), "pe": r.get("f9"),
                "pb": r.get("f23"), "mktcap_yi": yi(r.get("f20"))} for r in rows]
    similar, nearest = [], []
    scaled_pes, scaled_pbs = [], []
    if mktcap_yi:
        import math
        nearest = sorted(samples, key=lambda s: abs(math.log((s["mktcap_yi"] or mktcap_yi) / mktcap_yi)))[:3]
        # 体量相近（0.3x~3x）才是真可比；板块前 N 大里没有就如实说明，不硬凑
        similar = sorted([s for s in samples if s["mktcap_yi"]
                          and 0.3 * mktcap_yi <= s["mktcap_yi"] <= 3 * mktcap_yi],
                         key=lambda s: s["mktcap_yi"])[:3]
        # 剔除体量差 10 倍以上的巨头，避免大盘股把中位数带偏（小弟股必需）
        keep = [s for s in samples if s["mktcap_yi"] and s["mktcap_yi"] <= mktcap_yi * 10]
        scaled_pes = [s["pe"] for s in keep if isinstance(s["pe"], (int, float)) and s["pe"] > 0]
        scaled_pbs = [s["pb"] for s in keep if isinstance(s["pb"], (int, float)) and s["pb"] > 0]
    return {
        "board": bk, "industry": board_name or industry, "pe_n": len(pes), "pb_n": len(pbs),
        "pe_median": round(statistics.median(pes), 2) if pes else None,
        "pb_median": round(statistics.median(pbs), 2) if pbs else None,
        "pe_median_scaled": round(statistics.median(scaled_pes), 2) if scaled_pes else None,
        "pb_median_scaled": round(statistics.median(scaled_pbs), 2) if scaled_pbs else None,
        "scaled_n": len(scaled_pes),
        "samples": samples, "similar_by_size": similar, "nearest_by_size": nearest,
    }


# ---------------------------------------------------------------- 单只采集

def collect_one(code, want_peers=True, use_push2=True, quote=None):
    secid, tpref, sfx = market_of(code)
    secucode = code + "." + sfx
    m = {"code": code, "secid": secid, "market": {"sh": "沪市", "sz": "深市", "bj": "北交所"}[tpref]}
    if quote:                       # 腾讯行情先行注入，同业对比需要市值口径
        m["name"] = quote.get("name")
        m["pe_ttm"] = quote.get("pe_ttm")
        m["pb"] = quote.get("pb")
        m["mktcap_yi"] = quote.get("total_mktcap_yi")
        m["float_mktcap_yi"] = quote.get("float_mktcap_yi")

    # B1) 公司概况（行业/主营/省份/上市/员工/实控人）
    try:
        rows = f10("RPT_F10_BASIC_ORGINFO", secucode, size=1, sort_col=None)
        if rows:
            r = rows[0]
            m.update({
                "name": r.get("SECURITY_NAME_ABBR") or r.get("STR_NAMEA"),
                "org_name": r.get("ORG_NAME"), "em_industry": r.get("EM2016"),
                "csrc_industry": r.get("INDUSTRYCSRC1"), "province": r.get("PROVINCE"),
                "address": r.get("ADDRESS"), "listing_date": (r.get("LISTING_DATE") or "")[:10],
                "emp_num": r.get("EMP_NUM"), "chairman": r.get("CHAIRMAN"),
                "president": r.get("PRESIDENT"), "actual_holder": r.get("ACTUAL_HOLDER"),
                "main_business": (r.get("MAIN_BUSINESS") or "").strip().replace("\n", " ")[:400],
                "security_type": r.get("SECURITY_TYPE"), "org_web": r.get("ORG_WEB"),
            })
            if r.get("EM2016"):
                m["industry"] = r["EM2016"].split("-")[-1]
            elif r.get("INDUSTRYCSRC1"):
                m["industry"] = r["INDUSTRYCSRC1"].split("-")[-1]
    except Exception as e:
        m["error_orginfo"] = str(e)[:80]

    # B2) 近 3 期利润表
    try:
        m["income"] = [{
            "period": r.get("REPORT_DATE_NAME"), "notice": (r.get("NOTICE_DATE") or "")[:10],
            "revenue_yi": yi(r.get("TOTAL_OPERATE_INCOME")),
            "revenue_yoy": num(r.get("TOTAL_OPERATE_INCOME_YOY")),
            "parent_netprofit_yi": yi(r.get("PARENT_NETPROFIT")),
            "parent_netprofit_yoy": num(r.get("PARENT_NETPROFIT_YOY")),
            "deduct_netprofit_yi": yi(r.get("DEDUCT_PARENT_NETPROFIT")),
            "deduct_netprofit_yoy": num(r.get("DEDUCT_PARENT_NETPROFIT_YOY")),
            "rd_expense_yi": yi(r.get("RESEARCH_EXPENSE")),
        } for r in f10("RPT_F10_FINANCE_GINCOME", secucode, size=3)]
    except Exception as e:
        m["income"] = []
        m["error_income"] = str(e)[:80]

    # B3) 近 3 期主要指标
    try:
        m["ratios"] = [{
            "period": r.get("REPORT_DATE_NAME"), "eps": r.get("EPSJB"), "bps": r.get("BPS"),
            "gross_margin": num(r.get("XSMLL")), "net_margin": num(r.get("XSJLL")),
            "roe": num(r.get("ROEJQ")), "debt_ratio": num(r.get("ZCFZL")),
            "current_ratio": num(r.get("LD")), "quick_ratio": num(r.get("SD")),
            "ocf_per_share": num(r.get("MGJYXJJE"), 3), "ocf_to_rev": num(r.get("JYXJLYYSR")),
        } for r in f10("RPT_F10_FINANCE_MAINFINADATA", secucode, size=3)]
    except Exception as e:
        m["ratios"] = []
        m["error_ratios"] = str(e)[:80]

    # B4) 股东户数
    try:
        m["holders"] = [{
            "end_date": (r.get("END_DATE") or "")[:10], "holder_num": r.get("HOLDER_TOTAL_NUM"),
            "holder_num_ratio": num(r.get("TOTAL_NUM_RATIO")),
            "avg_free_shares": r.get("AVG_FREE_SHARES"), "hold_focus": r.get("HOLD_FOCUS"),
        } for r in f10("RPT_F10_EH_HOLDERNUM", secucode, size=2, sort_col="END_DATE")]
    except Exception:
        m["holders"] = []

    # B5) 十大流通股东中的机构
    try:
        rows = f10("RPT_F10_EH_FREEHOLDERS", secucode, size=12, sort_col="END_DATE")
        if rows:
            end = (rows[0].get("END_DATE") or "")[:10]
            cur = [r for r in rows if (r.get("END_DATE") or "")[:10] == end]
            inst = [r for r in cur if str(r.get("IS_HOLDORG")) in ("1", "True", "true")]
            m["inst_holders"] = {
                "end_date": end, "inst_count": len(inst),
                "inst_ratio_sum": round(sum(float(r.get("FREE_HOLDNUM_RATIO") or 0) for r in inst), 2),
                "top": [{"name": r.get("HOLDER_NAME"), "ratio": num(r.get("FREE_HOLDNUM_RATIO")),
                         "change": r.get("HOLD_NUM_CHANGE"), "type": r.get("HOLDER_TYPE")}
                        for r in cur[:5]],
            }
        else:
            m["inst_holders"] = None
    except Exception:
        m["inst_holders"] = None

    # C) 最近公告
    try:
        d = http_json("https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=6"
                      "&page_index=1&ann_type=A&client_source=web&stock_list=" + code)
        m["announcements"] = [{"date": (x.get("notice_date") or "")[:10],
                               "title": (x.get("title") or "").split(":", 1)[-1]}
                              for x in (d.get("data") or {}).get("list", [])[:6]]
    except Exception:
        m["announcements"] = []

    # D) push2 增强（行业名/概念板块/地域/PE动/ROE）—— 限流频繁，失败不影响主结论
    if use_push2:
        try:
            u = ("stock/get?invt=2&fltt=2&fields=f57,f58,f84,f85,f105,f116,f117,f127,f128,f162,"
                 "f167,f173,f183,f184,f185,f186,f187&secid=" + secid)
            d = push2_json(u).get("data") or {}
            if d:
                m["industry_em"] = d.get("f127")
                m["region_board"] = d.get("f128")
                m["pe_dyn"] = num(d.get("f162"))
                m["roe_latest"] = num(d.get("f173"))
                if not m.get("industry") and d.get("f127"):
                    m["industry"] = d["f127"]
        except Exception:
            pass

    # 兜底：行业名缺失时用概念板块首条 / 证监会行业
    if not m.get("industry"):
        m["industry"] = m.get("industry_em") or (m.get("csrc_industry") or "").split("-")[-1] or None

    # 比率兜底（push2 失败时用 MAINFINADATA 最近一期）
    if m.get("ratios"):
        r0 = m["ratios"][0]
        m.setdefault("gross_margin", r0.get("gross_margin"))
        m.setdefault("net_margin", r0.get("net_margin"))
        if not m.get("roe_latest"):
            m["roe_latest"] = r0.get("roe")

    if want_peers:
        try:
            m["peers"] = peers_comparison(m.get("industry"), secid=secid,
                                          mktcap_yi=m.get("mktcap_yi"),
                                          em_industry=m.get("em_industry"))
        except Exception:
            m["peers"] = None
    return m


# ---------------------------------------------------------------- 渲染

def render(m):
    L = []
    name = m.get("name") or m.get("org_name") or m["code"]
    L.append("===== 元数据 %s %s (%s) =====" % (m["code"], name, m.get("market")))
    L.append("行业: %s%s | 证监会行业: %s | 地域: %s/%s | 上市: %s | 员工: %s | 实控人: %s | 董事长: %s"
             % (nz(m.get("industry")),
                ("（东财概念板块: %s）" % m["region_board"]) if m.get("region_board") else "",
                nz(m.get("csrc_industry")), nz(m.get("province")), nz(m.get("region_board")),
                nz(m.get("listing_date")), nz(m.get("emp_num")),
                nz(m.get("actual_holder")), nz(m.get("chairman"))))
    if m.get("main_business"):
        L.append("主营业务: %s" % m["main_business"])
    L.append("估值: PE(TTM) %s | PE(动) %s | PB %s | 总市值 %s亿 | 流通市值 %s亿 | ROE(最近一期) %s%%"
             % (nz(m.get("pe_ttm")), nz(m.get("pe_dyn")), nz(m.get("pb") or m.get("pb_em")),
                nz(m.get("mktcap_yi")), nz(m.get("float_mktcap_yi")), nz(m.get("roe_latest"))))
    q = m.get("quote") or {}
    L.append("行情: 现价 %s | 涨跌幅 %s%% | 换手 %s%% | 振幅 %s%%"
             % (nz(q.get("price")), nz(q.get("chg_pct")), nz(q.get("turnover_pct")),
                nz(q.get("amplitude_pct"))))
    for i, r in enumerate(m.get("income") or []):
        tag = "最近一期" if i == 0 else "前%d期" % i
        L.append("财务[%s %s 披露%s]: 营收 %s亿(同比 %s%%) | 归母净利 %s亿(同比 %s%%) | 扣非 %s亿(同比 %s%%) | 研发 %s亿"
                 % (tag, nz(r.get("period")), nz(r.get("notice")), nz(r.get("revenue_yi")),
                    nz(r.get("revenue_yoy")), nz(r.get("parent_netprofit_yi")),
                    nz(r.get("parent_netprofit_yoy")), nz(r.get("deduct_netprofit_yi")),
                    nz(r.get("deduct_netprofit_yoy")), nz(r.get("rd_expense_yi"))))
    for i, r in enumerate(m.get("ratios") or []):
        tag = "最近一期" if i == 0 else "前%d期" % i
        L.append("指标[%s %s]: 毛利率 %s%% | 净利率 %s%% | ROE %s%% | 资产负债率 %s%% | 流动比 %s | 速动比 %s | 每股经营现金流 %s元"
                 % (tag, nz(r.get("period")), nz(r.get("gross_margin")), nz(r.get("net_margin")),
                    nz(r.get("roe")), nz(r.get("debt_ratio")), nz(r.get("current_ratio")),
                    nz(r.get("quick_ratio")), nz(r.get("ocf_per_share"))))
    for h in m.get("holders") or []:
        L.append("股东户数[%s]: %s 户 (环比 %s%%) | 户均流通股 %s | 集中度 %s"
                 % (nz(h.get("end_date")), nz(h.get("holder_num")), nz(h.get("holder_num_ratio")),
                    nz(h.get("avg_free_shares")), nz(h.get("hold_focus"))))
    ih = m.get("inst_holders")
    if ih:
        L.append("机构持仓[%s]: 前十流通股东中机构 %s 家, 合计占流通 %s%% | 前列: %s"
                 % (nz(ih.get("end_date")), ih.get("inst_count"), ih.get("inst_ratio_sum"),
                    "; ".join("%s %s%%" % (x.get("name"), x.get("ratio"))
                              for x in (ih.get("top") or [])[:3])))
    for a in m.get("announcements") or []:
        L.append("公告 %s: %s" % (a.get("date"), a.get("title")))
    p = m.get("peers")
    if p:
        if p.get("pe_median") is not None or p.get("pb_median") is not None:
            L.append("同业对比[%s 板块%s, PE样本%d只]: PE(TTM) 中位数 %s | PB 中位数 %s"
                     % (nz(p.get("industry")), nz(p.get("board")), p.get("pe_n") or 0,
                        nz(p.get("pe_median")), nz(p.get("pb_median"))))
            if p.get("pe_median_scaled") is not None:
                L.append("  （剔除体量>10倍巨头后, %d 只样本）PE 中位数 %s | PB 中位数 %s"
                         % (p.get("scaled_n") or 0, nz(p.get("pe_median_scaled")),
                            nz(p.get("pb_median_scaled"))))
            L.append("  大盘样本: %s" % "; ".join("%s(%s) PE%s/PB%s" % (x["name"], x["code"], nz(x["pe"]), nz(x["pb"]))
                                                 for x in (p.get("samples") or [])[:5]))
            if p.get("similar_by_size"):
                L.append("  市值相近可比公司(0.3~3倍): %s" % "; ".join(
                    "%s(%s) 市值%s亿 PE%s/PB%s" % (x["name"], x["code"], nz(x["mktcap_yi"]),
                                                   nz(x["pe"]), nz(x["pb"]))
                    for x in p["similar_by_size"]))
            elif p.get("nearest_by_size"):
                L.append("  市值相近可比公司: 板块内无 0.3~3 倍体量样本（本股体量显著小于板块样本）;"
                         " 板块内体量最接近: %s"
                         % "; ".join("%s 市值%s亿" % (x["name"], nz(x["mktcap_yi"]))
                                     for x in p["nearest_by_size"]))
        else:
            L.append("同业对比: %s" % nz(p.get("note"), dash="未获取"))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--codes", dest="codes_csv")
    ap.add_argument("--file")
    ap.add_argument("--json")
    ap.add_argument("--peers", type=int, default=10, help="同业样本数（0=不取）")
    ap.add_argument("--no-push2", action="store_true", help="跳过限流频繁的 push2 增强源")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    codes = list(a.codes or [])
    if a.codes_csv:
        codes += [c.strip() for c in a.codes_csv.split(",") if c.strip()]
    if a.file:
        with open(a.file) as f:
            codes += [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not codes and not sys.stdin.isatty():
        codes += [l.strip() for l in sys.stdin if l.strip() and not l.startswith("#")]
    codes = [c.split(".")[0].strip() for c in codes]
    seen, uniq = set(), []
    for c in codes:
        if c.isdigit() and len(c) == 6 and c not in seen:
            seen.add(c)
            uniq.append(c)
    if not uniq:
        print("用法: python3 collect_stock_meta.py 600584 002371 920212   (或 --file / --codes)")
        return 1

    quotes = tencent_quotes(uniq)
    with ThreadPoolExecutor(max_workers=6) as ex:
        metas = list(ex.map(lambda c: collect_one(c, want_peers=a.peers > 0,
                                                  use_push2=not a.no_push2,
                                                  quote=quotes.get(c)), uniq))
    for m in metas:
        q = quotes.get(m["code"])
        if q:
            m["quote"] = q
            m["pe_ttm"] = m.get("pe_ttm") or q.get("pe_ttm")
            m["pb"] = m.get("pb") or q.get("pb")
            m["mktcap_yi"] = m.get("mktcap_yi") or q.get("total_mktcap_yi")
            m["float_mktcap_yi"] = m.get("float_mktcap_yi") or q.get("float_mktcap_yi")
            m["name"] = m.get("name") or q.get("name")

    if not a.quiet:
        print("DATA_TIMESTAMP: %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
        print("样本数: %d 只 | 数据源统计: urllib %d / curl %d / 失败 %d"
              % (len(metas), _http_stats["urllib"], _http_stats["curl"], _http_stats["fail"]))
        print()
        for m in metas:
            print(render(m))
            print()
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "stocks": metas},
                      f, ensure_ascii=False, indent=1)
        print("JSON 已写入: %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
