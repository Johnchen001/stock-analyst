#!/usr/bin/env python3
"""Generate a comprehensive PDF briefing from markdown source.

One section per page. Strips all ** markers from output.

Usage:
  gen_briefing_pdf.py <input.md> <output.pdf>
"""
import sys, os, re
from fpdf import FPDF

EMOJI_MAP = {
    "\U0001f4ca": "[图表]",
    "\U0001f3e0": "[国内]",
    "\U0001f4cc": "[关注]",
    "\U0001f514": "[提醒]",
    "\U0001f4c8": "[上涨]",
    "\u26a0": "[警告]",
    "\ufe0f": "",
}

def clean_text(t):
    """Remove ** markers and emoji, return clean string."""
    t = t.replace('**', '')
    for k, v in EMOJI_MAP.items():
        t = t.replace(k, v)
    return t


class BriefingPDF(FPDF):
    MARGIN = 15

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        font_path = "/System/Library/Fonts/STHeiti Light.ttc"
        font_bold_path = "/System/Library/Fonts/STHeiti Medium.ttc"
        self.add_font("ST", "", font_path)
        self.add_font("ST", "B", font_bold_path)

    def footer(self):
        self.set_y(-15)
        self.set_font("ST", "", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"第 {self.page_no()}/{{nb}}", align="C")

    def p(self, text, size=9, bold=False, color=None, indent=0, line_h=5.5):
        """Safe paragraph with margin protection."""
        self.set_font("ST", "B" if bold else "", size)
        if color:
            self.set_text_color(*color)
        x = self.MARGIN + indent
        avail = self.w - self.MARGIN - self.r_margin - indent
        if avail < 20:
            self.add_page()
            x = self.MARGIN + indent
            avail = self.w - self.MARGIN - self.r_margin - indent
        self.set_x(x)
        self.multi_cell(avail, line_h, clean_text(text))
        self.set_text_color(0, 0, 0)


def _render_table(pdf, rows):
    """Render markdown table rows as structured text."""
    if len(rows) < 2:
        return
    header = [c.strip() for c in rows[0].strip('|').split('|')]
    data_rows = rows[2:]

    for dr in data_rows:
        cells = [c.strip() for c in dr.strip('|').split('|')]
        while len(cells) < len(header):
            cells.append('')
        cells = cells[:len(header)]

        line_parts = []
        for h, c in zip(header, cells):
            if c and c != '-':
                c_clean = clean_text(c)
                line_parts.append(f"{h}: {c_clean}")
        if line_parts:
            pdf.p("  " + " | ".join(line_parts), size=8, indent=3, line_h=5)


def generate_briefing_pdf(md_path, output_pdf):
    with open(md_path, 'r') as f:
        text = f.read()

    pdf = BriefingPDF()
    pdf.alias_nb_pages()

    lines = text.split('\n')

    # Extract date for cover
    date_line = ""
    for line in lines:
        if '2026' in line and '月' in line:
            date_line = clean_text(line.strip().lstrip('#').strip())
            break

    # ── Cover page ──
    pdf.add_page()
    pdf.ln(55)
    pdf.set_font("ST", "B", 26)
    pdf.cell(0, 16, "A股晨间简报", align="C", new_x="LMARGIN", new_y="NEXT")
    if date_line:
        pdf.set_font("ST", "", 14)
        pdf.cell(0, 12, date_line, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("ST", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 6, "本简报基于公开市场信息整理，不构成投资建议。股市有风险，投资需谨慎。")
    pdf.set_text_color(0, 0, 0)

    # ── Content pages ──
    in_table = False
    table_rows = []
    first_section = True  # first ## section doesn't need page break

    for line in lines:
        raw = line.strip()
        if not raw:
            if in_table and table_rows:
                pdf.p("", size=5)
                _render_table(pdf, table_rows)
                table_rows = []
                in_table = False
                pdf.ln(2)
            else:
                pdf.ln(2)
            continue

        # Table detection
        if raw.startswith('|') and raw.count('|') >= 3:
            if not in_table:
                in_table = True
                table_rows = [raw]
            else:
                table_rows.append(raw)
            continue
        else:
            if in_table and table_rows:
                pdf.p("", size=5)
                _render_table(pdf, table_rows)
                table_rows = []
                in_table = False
                pdf.ln(2)

        if raw == '---':
            y = pdf.get_y()
            if y < pdf.h - 25:
                pdf.set_draw_color(180, 180, 180)
                pdf.line(pdf.MARGIN, y, pdf.w - pdf.r_margin, y)
            pdf.ln(4)
            continue

        if raw.startswith('### '):
            pdf.p(raw[4:], size=10, bold=True, color=(50, 50, 50), line_h=6)
            pdf.ln(1)

        elif raw.startswith('## '):
            # One content section = one page
            if first_section:
                pdf.add_page()
                first_section = False
            else:
                pdf.add_page()
            pdf.p(raw[3:], size=15, bold=True, color=(0, 60, 140), line_h=10)
            pdf.ln(4)

        elif raw.startswith('>'):
            pdf.p(raw.lstrip('>').strip(), size=8, color=(100, 100, 100), indent=3, line_h=4.5)

        elif raw.startswith('- ') or raw.startswith('* '):
            content = raw[2:]
            pdf.p("• " + content, size=9, indent=5, line_h=5.5)

        else:
            pdf.p(raw, size=9, line_h=5.5)

    # Flush remaining table
    if in_table and table_rows:
        pdf.p("", size=5)
        _render_table(pdf, table_rows)

    # ── Disclaimer on last page ──
    pdf.ln(8)
    y = pdf.get_y()
    if y < pdf.h - 30:
        pdf.set_draw_color(180, 180, 180)
        pdf.line(pdf.MARGIN, y, pdf.w - pdf.r_margin, y)
        pdf.ln(4)
        pdf.p(
            "免责声明：本简报所有内容均基于公开信息整理，仅为信息分享，不构成对任何人的投资建议或要约。"
            "投资者据此操作，风险自担。市场有风险，投资需谨慎。",
            size=8, color=(120, 120, 120), line_h=4.5
        )

    pdf.output(output_pdf)
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: gen_briefing_pdf.py <input.md> <output.pdf>")
        sys.exit(1)
    md_path = os.path.expanduser(sys.argv[1])
    pdf_path = os.path.expanduser(sys.argv[2])
    if not os.path.exists(md_path):
        print(f"❌ Input not found: {md_path}")
        sys.exit(1)
    generate_briefing_pdf(md_path, pdf_path)
    print(f"✅ PDF: {pdf_path}")


if __name__ == "__main__":
    main()
