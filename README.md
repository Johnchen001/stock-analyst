# A股晨间简报 · Hermes Skill

> 每个交易日早上，自动产出一份可直接阅读、可直接推送的 **A股晨间简报 PDF**。
> 五模块结构 · 蓝白版式 · 每章独立成页 · 数据全部来自公开接口 · 附微信推送与 cron 配置。

这是一个给 [Hermes Agent](https://hermes-agent.nousresearch.com/docs) 的技能包（skill）。
Hermes 加载技能后，说一句「发早报」就能端到端跑完：判断交易日 → 采集行情/新闻/榜单 →
按规范写五模块 → 渲染 PDF → 推送微信。

---

## 目录

- [它能产出什么](#它能产出什么)
- [仓库结构](#仓库结构)
- [安装](#安装)
- [快速开始](#快速开始)
- [配置微信推送](#配置微信推送)
- [定时任务](#定时任务)
- [数据源与可靠性](#数据源与可靠性)
- [依赖](#依赖)
- [常见问题](#常见问题)
- [说明与免责](#说明与免责)

---

## 它能产出什么

一份 A4、9–12 页的 PDF，固定五章，每章从新的一页开始：

| 模块            | 内容                    | 硬性要求                                  |
| ------------- | --------------------- | ------------------------------------- |
| 一、隔夜市场与重大新闻   | 隔夜美股、国际事件、国内政策、产业动态   | ≥10 条，**每条标注对 A 股板块的利好/利空**           |
| 二、昨日 A 股收盘回顾  | 八大指数点位与涨跌幅、港股、强势/下跌板块 | 板块必须带**个股名称 + 6 位代码**                 |
| 三、省市投资动态（江浙沪） | 各省细分领域与对应上市公司         | 禁止「某省大力发展 X」式空话，**必须落到公司与代码**         |
| 四、昨日大涨股分析     | 每日精选 5 只，每只 ≥150 字    | 必须带 **【元数据】【判定】【事件】** 三段 + 末尾「昨日判定验证」 |
| 五、今日关注与推荐     | ≥10 支，分五类             | 新股申购需**细分领域 + 名称 + 代码 + 申购日期 + 发行价**  |

个股分析不靠新闻转述，而是先跑 `scripts/collect_stock_meta.py` 取公司元数据
（行业/主营/市值/PE/PB/近三期业绩/毛利率/ROE/负债率/股东户数/机构持仓/公告/同业中位数），
再据此判定「基本面驱动 / 题材资金驱动 / 混合（预期先行）」——规范见
`references/company-metadata-analysis.md`。

---

## 仓库结构

```
.
├── SKILL.md                           # 主手册：交易日判断 → 数据采集 → 撰写规范 → PDF → 推送 → cron → 排错
├── references/
│   ├── company-metadata-analysis.md   # 元数据驱动个股分析的强制规范
│   ├── eastmoney-stock-ranking-api.md # 东财排序/板块/龙虎榜接口字段详解
│   ├── briefing-sources-and-format.md # 数据源清单与通用内容模式
│   ├── pdf-layout-spec.md             # PDF 版式规范 v2（蓝白）：页面/字体/配色/分页/自检清单
│   ├── watchlist-daily-report.md      # 姊妹任务：自选股日报六模块口径
│   └── wechat-pdf-delivery.md         # 微信 iLink 发送细节与 API 签名
└── scripts/
    ├── collect_stock_meta.py          # 公司元数据一次性采集器（沪深北通用，多源降级）
    └── gen_briefing_pdf_v2.py         # markdown → PDF 渲染器（宋体小四 12pt，溢出自适应压排）
```

---

## 安装

```bash
git clone <this-repo> ~/.hermes/skills/finance/a-share-morning-briefing
```

或直接把整个文件夹拷进 `~/.hermes/skills/finance/`。
Hermes 启动时会扫描该目录，之后提到「发早报」「晨间简报」「今日早报」即会自动加载本技能。

验证是否被识别：

```bash
hermes skills list | grep a-share
```

---

## 快速开始

```bash
# 1) 装依赖
pip install fpdf2 fonttools

# 2) 采一只股票的元数据，确认数据源通
python3 scripts/collect_stock_meta.py 600584

# 3) 把 markdown 渲染成 PDF
python3 scripts/gen_briefing_pdf_v2.py /tmp/morning_briefing_YYYYMMDD.md ./out.pdf
```

在 Hermes 里最简单的用法就是一句话：

```
发早报
```

它会按 `SKILL.md` §3–§7 自己走完全流程（含交易日判断、数据采集、撰写、渲染、推送）。

---

## 配置微信推送

推送是可选的，不配置也能生成 PDF。需要推送时在 `~/.hermes/.env` 写入你自己的 iLink Bot 凭据：

```dotenv
WEIXIN_TOKEN=<your-token>
WEIXIN_ACCOUNT_ID=<your-account-id>
WEIXIN_BASE_URL=https://ilinkai.weixin.qq.com
```

并把 `SKILL.md` 与 `references/wechat-pdf-delivery.md` 中的
`<YOUR_CHAT_ID>@im.wechat` 换成你自己的联系人 ID。

> 本仓库已脱敏：原作者的个人联系人 ID 已全部替换为 `<YOUR_CHAT_ID>` 占位符。

---

## 定时任务

`SKILL.md` §8 给了完整的 cron 配置。要点：

- 工作日 `0 8 * * 1-5`，一份 job 同时交付「早报 + 自选股日报」
- 非交易日（周末/法定节假日）让任务直接退出，**不要推送空报告**
- job 的 `deliver` 用 `local`：PDF 由任务内部脚本自己推微信，cron 再投递一次会重复轰炸
- 长假后第一个交易日，新闻模块必须覆盖**整个假期**，不能只写昨天

---

## 数据源与可靠性

全部为公开页面接口，无需 API key：

- **行情/榜单**：东方财富 `push2` 系列（指数、涨跌幅榜、板块、龙虎榜、新股日历）
- **快讯**：新浪财经 7×24 直播
- **元数据**：东财 F10（行业、主营、财报、股东、公告）

这些接口会限流、会 TLS 抖动、会改字段。`SKILL.md` §3.3 给了明确的回退阶梯：
同一 URL 重试 → 换主机（`push2` → `push2delay` → `82.push2`）→ 换客户端（curl 带浏览器 UA）→
最后才动用浏览器。`collect_stock_meta.py` 已内置多源降级，不要每次手动切。

---

## 依赖

| 项              | 说明                                                              |
| -------------- | --------------------------------------------------------------- |
| Python         | 3.10+                                                           |
| `fpdf2 >= 2.8` | PDF 渲染                                                          |
| `fonttools`    | 从 `.ttc` 抽取宋体字形                                                 |
| 中文字体           | 默认取 macOS 的 `Songti.ttc`；其他平台请改 `gen_briefing_pdf_v2.py` 顶部字体路径 |
| 微信 iLink Bot   | 仅推送环节需要，可跳过                                                     |

```bash
pip install fpdf2 fonttools
```

---

## 常见问题

**Q：接口返回空 / curl exit 52？**
东财限流。按 `SKILL.md` §3.3 换主机（`push2delay`）或换 curl 重取，别一上来就开浏览器。

**Q：盘前取个股涨跌幅全是 `-`？**
盘前没有实时数据，用 `fid=f171`（昨日涨跌幅）排序，不要用 `f3`。

**Q：PDF 里出现 `**` 或表格消失？**
v2 渲染器不解析 `**`（会原样输出），markdown 里只写纯文本；表格会渲染成结构化文本，不会丢。

**Q：微信发送报 `session not ready: ret=-2`？**
是 iLink 会话上下文过期，不是网关挂了。先在微信里给 bot 发一条消息，再重发；别反复重启网关。

**Q：生成的简报只有几行 / 内容很空？**
多半是模型超时或没按规范写。`SKILL.md` §5 给了「手动兜底路径」：自己采数据 → 写 markdown → 渲染 → 推送。

---

## 说明与免责

- 本仓库为技能文档 + 脚本，**不含任何账号凭据**；已对原作者个人信息做脱敏。
- 文档中出现的个股、板块、评级均为历史示例，**不构成任何投资建议**。
- 数据接口为第三方公开页面接口，稳定性与准确性由数据源决定；请遵守其使用条款。
