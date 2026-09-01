#!/bin/bash
# Morning briefing - uses current Hermes profile (当前会话)
# Generates briefing, converts to PDF, sends to WeChat

SCRIPT_DIR="$HOME/.hermes/scripts"
VENV_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python3"
HERMES_CLI="$HOME/.local/bin/hermes"
SEND_PDF_SCRIPT="$SCRIPT_DIR/send_wechat_pdf_retry.py"
CONTACT="o9cq800hCSIovrI8HvOMYOQ-QHAY@im.wechat"
PDF_GEN_SCRIPT="$SCRIPT_DIR/gen_briefing_pdf.py"

DATE_TODAY=$(date +%Y%m%d)
BRIEFING_FILE="/tmp/morning_briefing_current_${DATE_TODAY}.md"
PDF_FILE="$HOME/Desktop/${DATE_TODAY}_A股晨间简报.pdf"

# Check weekday (Mon-Fri)
DOW=$(date +%u)
if [ "$DOW" -gt 5 ]; then
    exit 0
fi

echo "[$(date '+%H:%M:%S')] Generating briefing using current session..."

# Use hermes CLI with a non-interactive chat query
# This runs against the default profile (current session's model)
"$VENV_PYTHON" -c "
import subprocess, sys
result = subprocess.run(
    ['$HERMES_CLI', 'chat', '-q', '''你是专业股票分析助手。今天是$(date '+%Y年%m月%d日')（$(date '+%A')）。

要求：
1. 用web_search确认今天是否为A股交易日
2. 若非交易日，只输出[SILENT]
3. 若是，生成完整晨间简报

简报包含四大模块：
一、新闻模块：昨夜今晨重大国内国际新闻及盘面影响
二、省市投资动态：重点江浙沪，细化到细分领域和具体公司名称
三、昨日大涨股分析：具体股票名称+代码及上涨原因
四、今日关注推荐（5-7支）：含打新（新股名称+代码）、上涨潜力股、优质股

语气客观专业中立，禁止买卖建议。数据通过web_search实时获取。
以【A股晨间简报】日期开头。'''],
    capture_output=True, text=True, timeout=600
)
out = result.stdout + result.stderr
with open('$BRIEFING_FILE', 'w') as f:
    f.write(out)
print('Done, wrote', len(out), 'chars')
" 2>/tmp/briefing_current_err.log

# Check result
if grep -q "\[SILENT\]" "$BRIEFING_FILE" 2>/dev/null; then
    rm -f "$BRIEFING_FILE"
    exit 0
fi

# Generate PDF and send
if [ -s "$BRIEFING_FILE" ] && [ "$(wc -c < "$BRIEFING_FILE")" -gt 200 ]; then
    echo "[$(date '+%H:%M:%S')] Generating PDF..."
    "$VENV_PYTHON" "$PDF_GEN_SCRIPT" "$BRIEFING_FILE" "$PDF_FILE" 2>/dev/null

    if [ -f "$PDF_FILE" ] && [ -s "$PDF_FILE" ]; then
        echo "[$(date '+%H:%M:%S')] Sending PDF to WeChat..."
        "$VENV_PYTHON" "$SEND_PDF_SCRIPT" "$CONTACT" "$PDF_FILE" 2>/dev/null
    fi
fi

rm -f "$BRIEFING_FILE"
exit 0
