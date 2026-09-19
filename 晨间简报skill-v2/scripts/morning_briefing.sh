#!/bin/bash
# Morning briefing generator for stock-analyst
# Called by cron job - no_agent mode: stdout = delivery content
# Silent (no stdout) = skip delivery (non-trading day)
# Now generates PDF and sends to WeChat

SCRIPT_DIR="$HOME/.hermes/scripts"
export PATH="$HOME/.local/bin:$PATH"
STOCK_ANALYST="$HOME/.local/bin/stock-analyst"
VENV_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python3"
SEND_PDF_SCRIPT="$SCRIPT_DIR/send_wechat_pdf_retry.py"
CONTACT="o9cq800hCSIovrI8HvOMYOQ-QHAY@im.wechat"
PDF_GEN_SCRIPT="$SCRIPT_DIR/gen_briefing_pdf.py"

DATE_TODAY=$(date +%Y%m%d)
BRIEFING_FILE="/tmp/morning_briefing_${DATE_TODAY}.md"
PDF_FILE="$HOME/Desktop/${DATE_TODAY}_A股晨间简报.pdf"

# === Step 1: Check if today is a trading day ===

# Check weekday (Mon-Fri)
DOW=$(date +%u)
if [ "$DOW" -gt 5 ]; then
    # Weekend - silent exit, no delivery
    exit 0
fi

# === Step 2: Generate briefing using stock-analyst profile ===
export HERMES_HOME="$HOME/.hermes/profiles/stock-analyst"

echo "[$(date '+%H:%M:%S')] Generating morning briefing..."
# Use perl-based timeout since macOS lacks 'timeout' command
perl -e 'alarm shift; exec @ARGV' 600 "$STOCK_ANALYST" chat -q "你是专业股票分析助手。今天是$(date '+%Y年%m月%d日')（$(date '+%A')）。现在是早上7:30。

请执行：
1. 用web_search确认今天是否为A股交易日
2. 若非交易日，输出'[SILENT]'并结束
3. 若是，生成**非常详尽的**完整晨间简报，内容必须丰富充实，不少于2000字。

简报要求（每部分必须达到指定篇幅）：

一、新闻模块（至少10条，每条含影响分析，总计约600-800字）：
昨夜今晨重大国内国际新闻，必须有：
- 隔夜美股表现（三大指数涨跌、科技股/中概股）
- 国际重大事件（地缘政治、汇率、大宗商品等）
- 国内政策/经济数据
- 产业重大新闻（半导体、新能源、AI等）
- 每一条后面加括号注明对A股相关板块的利好/利空影响

二、省市投资动态（约400字，重点江浙沪，每个省至少3个细分领域）：
- 每个细分领域必须对应到具体上市公司名称+代码
- 覆盖半导体、新能源、生物医药、人工智能、低空经济、光通信等

三、昨日大涨股分析（至少5支，每支150字以上）：
- 具体股票名称+代码+涨幅
- 详细分析上涨原因（基本面/消息面/资金面）
- 必须从龙虎榜或涨幅榜提取真实数据

四、今日关注推荐（至少10支，含详细信息）：
- 新股申购（细分领域+新股名称+代码+申购日期+发行价）
- 即将上市新股
- 上涨潜力股（代码+看好逻辑）
- 优质股/业绩预增股（代码+逻辑）
- 防御型/高股息标的（代码+逻辑）

语气客观专业中立，禁止买卖建议。数据必须通过web_search实时获取，确保时效性。" 2>/tmp/stock_analyst_err.log > "$BRIEFING_FILE"

# === Step 3: Check result ===
if grep -q "\[SILENT\]" "$BRIEFING_FILE" 2>/dev/null; then
    # Not a trading day - silent exit
    rm -f "$BRIEFING_FILE"
    exit 0
fi

# === Step 4: Generate PDF and send to WeChat ===
if [ -s "$BRIEFING_FILE" ] && [ "$(wc -c < "$BRIEFING_FILE")" -gt 200 ]; then
    echo "[$(date '+%H:%M:%S')] Briefing generated, generating PDF..."

    # Generate PDF from markdown
    "$VENV_PYTHON" "$PDF_GEN_SCRIPT" "$BRIEFING_FILE" "$PDF_FILE" 2>/dev/null

    if [ -f "$PDF_FILE" ] && [ -s "$PDF_FILE" ]; then
        echo "[$(date '+%H:%M:%S')] PDF generated: $PDF_FILE" >&2

        # Send PDF via WeChat only (no text output to cron)
        echo "[$(date '+%H:%M:%S')] Sending PDF to WeChat..." >&2
        "$VENV_PYTHON" "$SEND_PDF_SCRIPT" "$CONTACT" "$PDF_FILE" 2>/dev/null

        # Silent success - no stdout, only PDF delivery
        # (cron delivers stdout in no_agent mode, so empty = no duplicate text)
    else
        echo "[$(date '+%H:%M:%S')] PDF generation failed, falling back to text..." >&2
        # Fallback: send as text
        BRIEFING=$(cat "$BRIEFING_FILE")
        echo "$BRIEFING"
    fi
fi

# Cleanup
rm -f "$BRIEFING_FILE"
exit 0
