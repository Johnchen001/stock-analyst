#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股晨间简报 PDF 渲染 v2(蓝白版式,2026-10-28 定稿)

用法:
    python3 gen_briefing_pdf_v2.py <input.md> <output.pdf>

版式要素(与 references/pdf-layout-spec.md 一致):
  封面     白底蓝字,31pt 深蓝主标题 + 目录(带真实页码)+ 居中免责声明
  正文     宋体小四 12pt,行距 7.2mm,首行缩进 2 字
  章节     ## 标题深蓝 18.5pt,左侧蓝色竖条 + 浅蓝分隔线,每章新起一页
  模块一   每条新闻自动编号 1、2、3……(序号深蓝加粗)
  模块三   上海/江苏/浙江 独立成 15.5pt 深蓝粗体小标题
  模块四   大涨股分块:序号 + 股票名 15pt 加粗 + 代码 + 涨幅(红) + 行情行 +
           元数据 / 判定 / 事件 三段各起一行(标签深蓝加粗)
  模块五   分组小标题(新股申购/上涨潜力股/优质股与业绩预增/防御型与高股息标的)
           14pt 深蓝加粗 + 蓝色小方块;个股名(代码)加粗
  配色     蓝白为主:深蓝 #1D4E7A / 中蓝 #306FA3 / 浅蓝 #E2ECF6 / 细线 #CBD8E5;
           利好=红 #B22222、利空=绿 #007448(A股语义色,不随主题改)
  分页     章节自适应:一章零星溢出时按 0.96→0.80 压行距/段距塞进一页;
           压不进则正常跨页;带孤行控制(页底不留 1~2 行)

字体: 从 /System/Library/Fonts/Supplemental/Songti.ttc 提取
      Songti SC Regular(face 6)/ Bold(face 1),缓存在 $BRIEFING_FONT_CACHE
      或 ~/.cache/a-share-briefing/fonts。
依赖:  fpdf2 >= 2.8, fontTools
"""
import os
import re
import sys
import tempfile
from collections import namedtuple

from fpdf import FPDF

# ── 配色(蓝白) ────────────────────────────────────────────────────────
C_INK = (28, 28, 30)          # 正文
C_BRAND = (29, 78, 122)       # 主蓝(标题 / 强调)
C_ACCENT = (48, 111, 163)     # 中蓝(序号 / 分隔线)
C_BULL = (178, 34, 34)        # 利好(红)
C_BEAR = (0, 116, 72)         # 利空(绿)
C_GREY = (108, 112, 118)      # 次要信息
C_LIGHT = (150, 154, 160)     # 极次要
C_SOFT = (226, 236, 246)      # 浅蓝底纹
C_RULE = (203, 216, 229)      # 细分隔线

# ── 版面 ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = 210.0, 297.0
MARGIN_LR, MARGIN_T, MARGIN_B = 18.0, 19.0, 18.0
BODY_SIZE = 12.0              # 宋体小四
BODY_LH = 7.2                 # 正文行高 mm
FIRST_INDENT = BODY_SIZE * 2 * 0.352778  # 两字符缩进
HEAD_BAN = set("，。、；：？！）】》」』’”%,.;:?!)][" + "…")

Token = namedtuple("Token", "text bold size color width")


# ────────────────────────────────────────────────────────────────────
#  字体
# ────────────────────────────────────────────────────────────────────
def cache_dir():
    """字体缓存目录:优先 $BRIEFING_FONT_CACHE,其次 ~/.cache,最后系统临时目录。"""
    env = os.environ.get("BRIEFING_FONT_CACHE")
    if env:
        return os.path.expanduser(env)
    for base in (os.path.expanduser("~/.cache/a-share-briefing/fonts"),
                 os.path.join(tempfile.gettempdir(), "a-share-briefing-fonts")):
        try:
            os.makedirs(base, exist_ok=True)
            return base
        except OSError:
            continue
    return tempfile.gettempdir()


def ensure_fonts(cache_dir):
    """从 Songti.ttc 提取宋体 Regular / Bold 到缓存,返回两个路径。"""
    src = "/System/Library/Fonts/Supplemental/Songti.ttc"
    faces = ((6, "SongtiSC-Regular"), (1, "SongtiSC-Bold"))
    os.makedirs(cache_dir, exist_ok=True)
    out = {}
    for idx, name in faces:
        dst = os.path.join(cache_dir, name + ".ttf")
        if not (os.path.exists(dst) and os.path.getsize(dst) > 1_000_000):
            from fontTools.ttLib import TTCollection
            col = TTCollection(src)
            col.fonts[idx].save(dst)
        out[name] = dst
    return out["SongtiSC-Regular"], out["SongtiSC-Bold"]


# ────────────────────────────────────────────────────────────────────
#  排版基元
# ────────────────────────────────────────────────────────────────────
MARK_RE = re.compile(r"(利好：|利空：)")


def _plain_tokens(text):
    """中文逐字切,ASCII(数字/代码/百分比/括号)整段切,丢弃空白。"""
    toks, buf = [], ""
    for ch in text:
        if ord(ch) < 128 and not ch.isspace():
            buf += ch
            continue
        if buf:
            toks.append(buf)
            buf = ""
        if not ch.isspace():
            toks.append(ch)
    if buf:
        toks.append(buf)
    return toks


def tokenize(text):
    """利好/利空标记整体不拆,其余按 _plain_tokens。"""
    out = []
    for part in MARK_RE.split(text):
        if not part:
            continue
        if MARK_RE.fullmatch(part):
            out.append(part)
        else:
            out.extend(_plain_tokens(part))
    return out


class BriefingPDF(FPDF):
    def __init__(self, regular, bold, report_date, scale=1.0):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("SR", "", regular)
        self.add_font("SB", "", bold)
        self.set_margins(MARGIN_LR, MARGIN_T, MARGIN_LR)
        self.set_auto_page_break(False)
        self.alias_nb_pages()
        self.report_date = report_date
        self.chapter_pages = {}
        self._w_cache = {}
        self.scale = scale      # 行距/段距压缩系数,字号不变

    # -- 基础 --
    @property
    def page_bottom(self):
        return PAGE_H - MARGIN_B - 11.0

    def f(self, bold=False, size=BODY_SIZE):
        self.set_font("SB" if bold else "SR", "", size)

    def sw(self, text, bold, size):
        key = (text, bold, size)
        w = self._w_cache.get(key)
        if w is None:
            self.f(bold, size)
            w = self.get_string_width(text)
            self._w_cache[key] = w
        return w

    def footer(self):
        if self.page_no() == 1:      # 封面不画页脚
            return
        y = PAGE_H - 26.0
        self.set_draw_color(*C_RULE)
        self.set_line_width(0.2)
        self.line(MARGIN_LR, y, PAGE_W - MARGIN_LR, y)
        self.f(False, 8)
        self.set_text_color(*C_LIGHT)
        self.set_xy(MARGIN_LR, y + 1.2)
        self.cell(PAGE_W - 2 * MARGIN_LR, 6.4,
                  f"A股晨间简报 · {self.report_date} · 第 {self.page_no()}/{{nb}} 页",
                  align="C")

    # -- 组件 --
    def chapter_title(self, title):
        self.set_y(MARGIN_T)
        y0 = self.y
        self.set_fill_color(*C_BRAND)
        self.rect(MARGIN_LR, y0 + 1.0, 2.4, 9.0, "F")
        self.f(True, 18.5)
        self.set_text_color(*C_BRAND)
        self.set_xy(MARGIN_LR + 5.0, y0)
        self.cell(PAGE_W - 2 * MARGIN_LR - 5.0, 11, title)
        self.set_y(y0 + 13.0)
        self.set_draw_color(*C_ACCENT)
        self.set_line_width(0.7)
        self.line(MARGIN_LR, self.y, PAGE_W - MARGIN_LR, self.y)
        self.set_y(self.y + 5.0)

    def sub_title(self, text, size=13.5, gap_after=2.0, gap_before=2.5):
        gap_after *= self.scale
        gap_before *= self.scale
        self.ensure_room(size * 0.352778 * 1.9)
        self.set_y(self.y + gap_before)
        self.f(True, size)
        self.set_text_color(48, 48, 52)
        self.set_x(MARGIN_LR)
        self.multi_cell(PAGE_W - 2 * MARGIN_LR, size * 0.352778 * 1.55, text,
                        new_x="LMARGIN", new_y="NEXT")
        self.set_y(self.y + gap_after)

    def group_head(self, text):
        """模块五的分组小标题:加粗 + 前置蓝色方块。"""
        self.ensure_room(12.0 * self.scale)
        self.set_y(self.y + 2.6 * self.scale)
        y0 = self.y
        self.set_fill_color(*C_ACCENT)
        self.rect(MARGIN_LR, y0 + 1.6, 2.6, 5.2, "F")
        self.f(True, 14.0)
        self.set_text_color(*C_BRAND)
        self.set_xy(MARGIN_LR + 4.6, y0)
        self.cell(PAGE_W - 2 * MARGIN_LR - 4.6, 8.4, text)
        self.set_y(y0 + 10.2 * self.scale)

    def ensure_room(self, need):
        if self.y + need > self.page_bottom:
            self.add_page()
            self.set_y(MARGIN_T)

    # -- 富文本段落 --
    def rich_para(self, segs, size=BODY_SIZE, line_h=BODY_LH,
                  first_indent=FIRST_INDENT, gap_after=3.0, report_lead=None):
        """segs: [(text, bold, color)];report_lead 为可选首行前置 segment。"""
        line_h = line_h * self.scale
        gap_after = gap_after * self.scale
        avail = PAGE_W - 2 * MARGIN_LR - 1.5   # 安全余量,避免字形 bbox 贴边
        tokens = []
        for text, bold, color in segs:
            for tk in tokenize(text):
                w = self.sw(tk, bold, size)
                if w > avail * 0.9 and len(tk) > 1:
                    for ch in tk:
                        tokens.append(Token(ch, bold, size, color, self.sw(ch, bold, size)))
                else:
                    tokens.append(Token(tk, bold, size, color, w))

        # 首行前置(序号)宽度:占用首行缩进位
        lead_spec, lead_w = None, 0.0
        if report_lead is not None:
            lead_txt, lead_bold, lead_size, lead_color = report_lead
            lead_w = self.sw(lead_txt, lead_bold, lead_size)
            lead_spec = Token(lead_txt, lead_bold, lead_size, lead_color, lead_w)
            first_indent = 0.0

        lines, cur, cur_w = [], [], 0.0
        for tk in tokens:
            limit = avail - ((first_indent + lead_w) if not lines else 0.0)
            if cur and cur_w + tk.width > limit:
                if tk.text in HEAD_BAN and len(cur) > 1:
                    moved = [cur.pop()]
                    while len(moved) < 6 and moved[0].text in HEAD_BAN and len(cur) > 1:
                        moved.insert(0, cur.pop())
                    lines.append(cur)
                    newline = moved + [tk]
                    if sum(t.width for t in newline) > avail:
                        lines.append(moved)
                        newline = [tk]
                    cur = newline
                    cur_w = sum(t.width for t in cur)
                    continue
                lines.append(cur)
                cur, cur_w = [tk], tk.width
            else:
                cur.append(tk)
                cur_w += tk.width
        if cur:
            lines.append(cur)

        if lines:
            remain = self.page_bottom - self.y
            if len(lines) * line_h > remain and remain < 3 * line_h \
                    and self.y > MARGIN_T + 1.0:
                self.add_page()          # 孤行控制:不在页底只留 1~2 行

        for i, line in enumerate(lines):
            if self.y + line_h > self.page_bottom:
                self.add_page()
            if i == 0 and lead_spec is not None:
                x = MARGIN_LR
                x = self._draw_line([lead_spec], x, line_h)
            else:
                x = MARGIN_LR + (first_indent if i == 0 else 0.0)
            self._draw_line(line, x, line_h)
            self.set_y(self.y + line_h)
        self.set_y(self.y + gap_after)

    def _draw_line(self, tokens, x, line_h):
        self.set_xy(x, self.y)
        for tk in tokens:
            self.f(tk.bold, tk.size)
            self.set_text_color(*tk.color)
            self.cell(tk.width, line_h, tk.text)
        end_x = self.get_x()
        self.set_x(MARGIN_LR)
        return end_x

    def centered(self, text, size=10.0, color=C_GREY, gap_after=2.0):
        self.ensure_room(size * 0.352778 * 1.8)
        self.f(False, size)
        self.set_text_color(*color)
        self.set_x(MARGIN_LR)
        self.cell(PAGE_W - 2 * MARGIN_LR, size * 0.352778 * 1.7, text, align="C")
        self.set_y(self.y + size * 0.352778 * 1.7 + gap_after)

    def rule_line(self, gap_before=3.0, gap_after=3.0, color=C_RULE, width=0.2):
        self.ensure_room(gap_before + gap_after + 2)
        self.set_y(self.y + gap_before)
        self.set_draw_color(*color)
        self.set_line_width(width)
        self.line(MARGIN_LR, self.y, PAGE_W - MARGIN_LR, self.y)
        self.set_y(self.y + gap_after)


# ────────────────────────────────────────────────────────────────────
#  文本解析:利好 / 利空 着色
# ────────────────────────────────────────────────────────────────────
BRACKET_RE = re.compile(r"[（(][^（()）]*[）)]")
BULL_MARK = re.compile(r"(利好|利空)：")
STOCK_HEAD_RE = re.compile(r"^([\u4e00-\u9fa5A-Za-z\*]+\((?:\d{6})\))")


def split_brackets(text):
    """把段落切成 [(chunk, color_or_None)],括号内利好/利空片段着色。"""
    out, pos = [], 0
    for m in BRACKET_RE.finditer(text):
        inner = m.group(0)[1:-1]
        if not BULL_MARK.search(inner):
            continue
        if m.start() > pos:
            out.append((text[pos:m.start()], None))
        out.append((m.group(0)[0], None))
        marks = [(mm.start(), mm.group(1)) for mm in BULL_MARK.finditer(inner)]
        if marks[0][0] > 0:
            out.append((inner[:marks[0][0]], None))
        for i, (p, kind) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(inner)
            out.append((inner[p:end], C_BULL if kind == "利好" else C_BEAR))
        out.append((m.group(0)[-1], None))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], None))
    return out


def colored_segs(text, bold_first_stock=False):
    """返回 [(text, bold, color)]"""
    segs = []
    head = None
    if bold_first_stock:
        m = STOCK_HEAD_RE.match(text)
        if m:
            head, text = m.group(1), text[m.end():]
    if head:
        segs.append((head, True, C_INK))
    for chunk, color in split_brackets(text):
        if chunk:
            segs.append((chunk, False, color or C_INK))
    return segs


# ────────────────────────────────────────────────────────────────────
#  markdown 解析
# ────────────────────────────────────────────────────────────────────
DATE_RE = re.compile(r"^\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
CN_NUM = "一二三四五六七八九十"


def parse_md(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
        lines = text.split("\n")
    date, chapters, cur = "", [], None
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("## "):
            t = s[3:].strip()
            if DATE_RE.match(t) and len(t) <= 30:
                date = t
                continue
            cur = {"title": t, "blocks": []}
            chapters.append(cur)
            continue
        if s.startswith("# ") or cur is None:
            continue
        if s == "---":
            cur["blocks"].append(("hr", ""))
        elif s.startswith("### "):
            cur["blocks"].append(("sub", s[4:].strip()))
        elif s.startswith(">"):
            cur["blocks"].append(("quote", s.lstrip(">").strip()))
        elif s.startswith("- ") or s.startswith("* "):
            cur["blocks"].append(("bullet", s[2:].strip()))
        elif s.startswith("|"):
            cur["blocks"].append(("table", s))
        else:
            cur["blocks"].append(("para", s))
    m = re.search(r"数据时间截至\s*([^。，；;\n]+)", text)
    data_time = m.group(1).strip() if m else ""
    return {"date": date, "chapters": chapters, "data_time": data_time}


# ────────────────────────────────────────────────────────────────────
#  章节渲染
# ────────────────────────────────────────────────────────────────────
STOCK_RE = re.compile(r"^(\S+?)\((\d{6})\)[，,]\s*([^，,]+)[，,]\s*(.*)$", re.S)
SEG_RE = re.compile(r"【(元数据|判定|事件)】")
QUOTE_TAIL_RE = re.compile(r"^(.*?)。(.*)$", re.S)


def render_chapter(pdf, ch, idx, total, scale=1.0):
    pdf.scale = scale
    pdf.add_page()
    pdf.chapter_pages[ch["title"]] = pdf.page_no()
    pdf.chapter_title(ch["title"])

    blocks = ch["blocks"]
    if idx == 0:                     # 模块一:隔夜市场 → 自动编号
        n = 0
        for kind, text in blocks:
            if kind == "para":
                n += 1
                segs = colored_segs(text)
                pdf.rich_para(segs, report_lead=(f"{n}、", True, BODY_SIZE, C_BRAND))
            elif kind == "sub":
                pdf.sub_title(text)
            elif kind == "bullet":
                pdf.rich_para([("• ", True, C_BRAND)] + colored_segs(text))
            elif kind == "quote":
                render_quote(pdf, text)
    elif idx == 2:                   # 模块三:省市 → 省份名放大加号
        for kind, text in blocks:
            m = re.match(r"^(上海|江苏|浙江)：", text)
            if kind == "para" and m:
                render_province_para(pdf, m.group(1), text[m.end():])
            elif kind == "para":
                pdf.rich_para(colored_segs(text))
            elif kind == "sub":
                pdf.sub_title(text)
            elif kind == "quote":
                render_quote(pdf, text)
    elif idx == 3:                   # 模块四:大涨股 → 分块排版
        stock_no = 0
        for kind, text in blocks:
            if kind == "para" and "【元数据】" in text:
                stock_no += 1
                render_stock_block(pdf, text, stock_no)
            elif kind == "para":
                pdf.rich_para(colored_segs(text), size=11.0, line_h=6.6,
                              first_indent=11.0 * 2 * 0.352778, gap_after=3.0)
            elif kind == "sub":
                pdf.sub_title(text)
            elif kind == "quote":
                render_quote(pdf, text)
    elif idx == 4:                   # 模块五:关注与推荐
        for kind, text in blocks:
            if kind == "para" and re.match(r"^[^\s，：]{1,12}[：:]$", text):
                pdf.group_head(text)
            elif kind == "para":
                pdf.rich_para(colored_segs(text, bold_first_stock=True),
                              gap_after=2.6)
            elif kind == "sub":
                pdf.sub_title(text)
            elif kind == "quote":
                render_quote(pdf, text)
    else:
        for kind, text in blocks:
            if kind == "sub":
                pdf.sub_title(text)
            elif kind == "para":
                pdf.rich_para(colored_segs(text))
            elif kind == "bullet":
                pdf.rich_para([("• ", True, C_BRAND)] + colored_segs(text))
            elif kind == "quote":
                render_quote(pdf, text)
            elif kind == "hr":
                pdf.rule_line()


def render_province_para(pdf, province, body):
    pdf.ensure_room(26)
    pdf.set_y(pdf.y + 2.4 * pdf.scale)
    y0 = pdf.y
    pdf.set_fill_color(*C_BRAND)
    pdf.rect(MARGIN_LR, y0 + 1.4, 2.2, 6.2, "F")
    pdf.f(True, 15.5)
    pdf.set_text_color(*C_BRAND)
    pdf.set_xy(MARGIN_LR + 4.2, y0)
    pdf.cell(PAGE_W - 2 * MARGIN_LR - 4.2, 8.6, province)
    pdf.set_y(y0 + 9.4)
    pdf.set_draw_color(*C_RULE)
    pdf.set_line_width(0.25)
    pdf.line(MARGIN_LR + 4.2, pdf.y - 1.2, PAGE_W - MARGIN_LR, pdf.y - 1.2)
    pdf.set_y(pdf.y + 2.6 * pdf.scale)
    pdf.rich_para(colored_segs(body), size=11.5, line_h=7.0,
                  first_indent=11.5 * 2 * 0.352778, gap_after=4.2)


def render_stock_block(pdf, text, no):
    m = STOCK_RE.match(text)
    if not m:
        pdf.rich_para(colored_segs(text))
        return
    name, code, board, rest = m.groups()
    quote, tail = "", rest
    qm = QUOTE_TAIL_RE.match(rest)
    if qm:
        quote, tail = qm.group(1), qm.group(2)
    parts = [p for p in SEG_RE.split(tail) if p != ""]
    sections = []
    if len(parts) >= 6:
        for i in range(0, 6, 2):
            sections.append((parts[i], parts[i + 1]))

    pct = re.search(r"涨([\d.]+)%", quote)

    pdf.ensure_room(40)
    pdf.set_y(pdf.y + 3.0 * pdf.scale)
    y0 = pdf.y
    # 左侧序号竖条
    pdf.set_fill_color(*C_BRAND)
    pdf.rect(MARGIN_LR, y0 + 0.6, 2.0, 9.6, "F")
    # 序号
    pdf.f(True, 13.5)
    pdf.set_text_color(*C_ACCENT)
    pdf.set_xy(MARGIN_LR + 3.6, y0)
    pdf.cell(9.0, 9.0, f"{no:02d}")
    # 股票名
    pdf.f(True, 15.0)
    pdf.set_text_color(*C_INK)
    pdf.set_xy(MARGIN_LR + 14.0, y0)
    pdf.cell(pdf.sw(name, True, 15.0) + 1.0, 9.0, name)
    # 代码
    pdf.f(False, 10.5)
    pdf.set_text_color(*C_GREY)
    pdf.cell(pdf.sw(f"({code})", False, 10.5) + 1.0, 9.0, f"({code})")
    pdf.cell(3.0, 9.0, "")
    # 涨幅
    if pct:
        pdf.f(True, 14.0)
        pdf.set_text_color(*C_BULL)
        pdf.cell(pdf.sw(f"+{pct.group(1)}%", True, 14.0) + 1.0, 9.0, f"+{pct.group(1)}%")
    pdf.set_y(y0 + 10.2 * pdf.scale)
    # 行情行
    line = f"{board} · {quote}" if quote else board
    pdf.f(False, 10.5)
    pdf.set_text_color(*C_GREY)
    pdf.set_x(MARGIN_LR + 3.6)
    pdf.multi_cell(PAGE_W - 2 * MARGIN_LR - 3.6, 6.0, line,
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(pdf.y + 1.6 * pdf.scale)
    # 三段:元数据 / 判定 / 事件
    for label, content in sections:
        pdf.rich_para([(label, True, C_BRAND), ("　", False, C_INK)]
                      + colored_segs(content),
                      size=BODY_SIZE, line_h=BODY_LH,
                      first_indent=0.0, gap_after=1.8)
    pdf.set_y(pdf.y + 2.0 * pdf.scale)


def render_quote(pdf, text):
    pdf.rule_line(gap_before=3.0, gap_after=2.6)
    pdf.rich_para([(text, False, C_GREY)], size=9.5, line_h=5.4,
                  first_indent=0.0, gap_after=2.0)


# ────────────────────────────────────────────────────────────────────
#  封面
# ────────────────────────────────────────────────────────────────────
def draw_cover(pdf, doc, page_map):
    """蓝白封面:白底为主,蓝色只做点缀,避免整块深色显得太正式。"""
    pdf.add_page()

    # 顶部居中短蓝线 + 主标题
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(1.6)
    pdf.line(PAGE_W / 2 - 14, 34, PAGE_W / 2 + 14, 34)

    pdf.f(True, 31)
    pdf.set_text_color(*C_BRAND)
    pdf.set_xy(0, 45)
    pdf.cell(PAGE_W, 17, "A 股 晨 间 简 报", align="C")

    pdf.f(False, 13.5)
    pdf.set_text_color(*C_GREY)
    pdf.set_xy(0, 70)
    pdf.cell(PAGE_W, 9, doc["date"], align="C")

    pdf.f(False, 9.5)
    pdf.set_text_color(*C_LIGHT)
    pdf.set_xy(0, 81)
    pdf.cell(PAGE_W, 7, "隔夜市场 · 昨日复盘 · 江浙沪动态 · 大涨股 · 今日关注", align="C")

    # 分节信息条(浅蓝底)
    pdf.set_fill_color(*C_SOFT)
    pdf.rect(MARGIN_LR, 96, PAGE_W - 2 * MARGIN_LR, 0.0, "F")

    # 目录
    pdf.set_y(104)
    pdf.f(True, 12.5)
    pdf.set_text_color(*C_BRAND)
    pdf.set_x(MARGIN_LR + 2)
    pdf.cell(60, 8.6, "本 期 目 录")
    pdf.set_draw_color(*C_RULE)
    pdf.set_line_width(0.3)
    pdf.line(MARGIN_LR + 2, pdf.y + 9.2, PAGE_W - MARGIN_LR - 2, pdf.y + 9.2)

    y = 122.0
    for i, title in enumerate([c["title"] for c in doc["chapters"]]):
        page = page_map.get(title, "")
        pdf.f(True, 11)
        pdf.set_text_color(*C_ACCENT)
        pdf.set_xy(MARGIN_LR + 4, y)
        pdf.cell(14, 8, f"{i + 1:02d}")
        pdf.f(False, 13)
        pdf.set_text_color(*C_INK)
        pdf.cell(PAGE_W - 2 * MARGIN_LR - 40, 8, title)
        pdf.f(True, 11)
        pdf.set_text_color(*C_BRAND)
        pdf.set_xy(PAGE_W - MARGIN_LR - 16, y)
        pdf.cell(12, 8, f"P{page}", align="R")
        y += 13.0

    # 免责声明(居中)
    pdf.set_y(250)
    pdf.set_draw_color(*C_RULE)
    pdf.set_line_width(0.2)
    pdf.line(MARGIN_LR + 20, pdf.y, PAGE_W - MARGIN_LR - 20, pdf.y)
    pdf.set_y(pdf.y + 4.5)
    pdf.f(False, 10)
    pdf.set_text_color(*C_GREY)
    pdf.set_x(0)
    pdf.cell(PAGE_W, 7,
             "本简报基于公开市场信息整理，不构成投资建议。股市有风险，投资需谨慎。",
             align="C")
    pdf.set_y(pdf.y + 8)
    pdf.f(False, 8.5)
    pdf.set_text_color(*C_LIGHT)
    pdf.set_x(0)
    stamp = doc.get("data_time") or ""
    foot = f"数据时间截至 {stamp} · 仅供参考" if stamp else "仅供参考"
    pdf.cell(PAGE_W, 6, foot, align="C")


# ────────────────────────────────────────────────────────────────────
#  章节自适应:尽量把同一章内容压进一页
# ────────────────────────────────────────────────────────────────────
MIN_SCALE = 0.80          # 行距最多压到 80%(12pt 字对应 1.36 倍行距,仍是可读下限)
SCALE_STEPS = (0.96, 0.92, 0.88, 0.84, MIN_SCALE)


def _chapter_pages(regular, bold, date, ch, idx, total, scale):
    probe = BriefingPDF(regular, bold, date, scale=scale)
    render_chapter(probe, ch, idx, total, scale)
    return probe.page_no()


def best_scale_for_chapter(regular, bold, date, ch, idx, total):
    """返回让该章恰好 1 页的最大 scale;压不进一页则返回 1.0(正常跨页)。"""
    if _chapter_pages(regular, bold, date, ch, idx, total, 1.0) == 1:
        return 1.0
    for sc in SCALE_STEPS:
        if _chapter_pages(regular, bold, date, ch, idx, total, sc) == 1:
            return sc
    return 1.0


# ────────────────────────────────────────────────────────────────────
#  主流程
# ────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print("Usage: gen_briefing_pdf_v2.py <input.md> <output.pdf>")
        sys.exit(1)
    md_path, out_pdf = sys.argv[1], sys.argv[2]
    regular, bold = ensure_fonts(cache_dir())
    doc = parse_md(md_path)
    total = len(doc["chapters"])

    # 各章压缩系数:能一页装下就压一点点行距,避免末页只剩两三行
    scales = [best_scale_for_chapter(regular, bold, doc["date"], ch, idx, total)
              for idx, ch in enumerate(doc["chapters"])]

    # pass 1:只为拿到各章页码
    probe = BriefingPDF(regular, bold, doc["date"])
    probe.add_page()
    for idx, ch in enumerate(doc["chapters"]):
        render_chapter(probe, ch, idx, total, scales[idx])
    page_map = dict(probe.chapter_pages)

    # pass 2:正式输出
    pdf = BriefingPDF(regular, bold, doc["date"])
    draw_cover(pdf, doc, page_map)
    for idx, ch in enumerate(doc["chapters"]):
        render_chapter(pdf, ch, idx, total, scales[idx])
    pdf.set_title(f"A股晨间简报 {doc['date']}")
    pdf.set_subject("A股晨间简报 · 隔夜市场/昨日复盘/江浙沪动态/大涨股/今日关注")
    pdf.set_creator("gen_briefing_pdf_v2")
    pdf.output(out_pdf)
    print(f"OK {out_pdf} pages={pdf.page_no()}")


if __name__ == "__main__":
    main()
