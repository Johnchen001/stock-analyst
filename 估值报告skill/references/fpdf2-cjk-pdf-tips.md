# fpdf2 CJK PDF Rendering Tips

This reference covers the bugs, fixes, and patterns encountered when generating Chinese-language PDFs with fpdf2 (v2.8.4) using macOS system fonts.

## System Fonts (macOS)

| Font | Path | Use case |
|------|------|----------|
| Hiragino Sans GB | `/System/Library/Fonts/Hiragino Sans GB.ttc` | Clean modern CJK, preferred for reports |
| STHeiti Light/Medium | `/System/Library/Fonts/STHeiti Medium.ttc` | Sans-serif alternative |
| AppleSDGothicNeo | `/System/Library/Fonts/AppleSDGothicNeo.ttc` | Apple's Korean/Japanese/CJK |

All are .ttc (TrueType Collection) files. fpdf2 supports them directly — no need to extract individual .ttf.

```python
self.add_font('CJK', '', '/System/Library/Fonts/Hiragino Sans GB.ttc')
self.add_font('CJK', 'B', '/System/Library/Fonts/Hiragino Sans GB.ttc')
```

`uni=True` parameter is deprecated since v2.5.1 and can be omitted.

## The #1 Bug: "Not enough horizontal space to render a single character"

### Root Cause

fpdf2's `multi_cell()` auto-adjusts width based on current x position: `width = page_w - x - r_margin`. If x has drifted rightward (e.g., after a table, nested `cell()`, or previous `multi_cell`), the remaining width may be zero or negative.

### The Fix

Call `self.set_x(self.l_margin)` **before every text-writing method** in your custom class:

```python
class MyPDF(FPDF):
    def body_text(self, text):
        self.set_x(self.l_margin)  # ← CRITICAL
        self.set_font('CJK', '', 9.5)
        self.multi_cell(0, 5.2, text)

    def bullet_text(self, text, indent=10):
        self.set_x(self.l_margin)
        self.set_x(self.get_x() + indent)
        self.multi_cell(180 - indent, 5.2, '\u2022 ' + text)

    def note_text(self, text):
        self.set_x(self.l_margin)
        self.set_font('CJK', '', 8)
        self.multi_cell(0, 4.5, text)

    def section_title(self, title, level=1):
        self.set_x(self.l_margin)
        self.ln(4)
        # ... rest
```

### What triggers x drift

| Operation | Effect | Fix |
|-----------|--------|-----|
| `multi_cell(w=0, ...)` | Sets x to l_margin on exit — safe | None needed |
| `multi_cell(w=<specific>, ...)` | Sets x to l_margin on exit — safe | None needed |
| `cell(w, h, text, 0, 0)` (ln=0) | x moves right by w | Reset x before next multi_cell |
| `table_simple()` using set_xy mid-cell | x can get stuck at cell edge | Reset in calling method |
| Page break mid-table | x may not reset after add_page | Explicit set_x in auto-page-break handler |
| User-level methods that call multi_cell inside | x resets, but outer context may not know | Reset at top of every public method |

## Table Implementation

### Complete working pattern

```python
def table_simple(self, headers, rows, col_widths=None):
    n = len(headers)
    if col_widths is None:
        col_widths = [190/n] * n
    # Normalize to 190mm
    total = sum(col_widths)
    if total != 190:
        col_widths = [w * 190 / total for w in col_widths]
    
    # Header
    self.set_font('CJK', 'B', 8)
    self.set_fill_color(30, 70, 140)
    self.set_text_color(255, 255, 255)
    for i, h in enumerate(headers):
        self.cell(col_widths[i], 6, h, 1, 0, 'C', True)
    self.ln()
    
    # Rows
    self.set_font('CJK', '', 8)
    self.set_text_color(40, 40, 40)
    for row_idx, row in enumerate(rows):
        # Auto page break
        if self.get_y() > 270:
            self.add_page()
            # Re-draw header
            self.set_font('CJK', 'B', 8)
            self.set_fill_color(30, 70, 140)
            self.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                self.cell(col_widths[i], 6, h, 1, 0, 'C', True)
            self.ln()
            self.set_font('CJK', '', 8)
            self.set_text_color(40, 40, 40)
        
        fill = row_idx % 2 == 1
        if fill:
            self.set_fill_color(240, 245, 252)
        else:
            self.set_fill_color(255, 255, 255)
        
        for i, cell_text in enumerate(row):
            self.cell(col_widths[i], 5.5, str(cell_text), 1, 0, 'L', fill)
        self.ln()
    
    self.ln(2)
    self.set_x(self.l_margin)  # ← ALWAYS after table
```

## Multi-cell Height Calculation

When you need to know a multi_cell's height before rendering it (e.g., to set row height in a table):

```python
# fpdf2 < 2.7.4 — use split_only
lines = self.multi_cell(width, 5, text, split_only=True)
row_height = len(lines) * 5

# fpdf2 >= 2.7.4 — use dry_run=True, output="LINES"
lines = self.multi_cell(width, 5, text, dry_run=True, output="LINES")
row_height = len(lines) * 5
```

## Sensitivity Table (DCF Matrix)

For a DCF sensitivity table (WACC × Growth rate):

```python
# Use table_simple but highlight the base-case cell
# Strategy: after rendering all cells, draw a rectangle on the base-case cell
sens_headers = ['WACC \\ g', 'g=2.0%', 'g=2.5%', 'g=3.0%', 'g=3.5%', 'g=4.0%']
sens_rows = [
    ['WACC=6.2%', '72.3', '85.7', '105.8', '139.6', '207.4'],
    ['WACC=6.7%', '60.8', '70.6', '84.2', '105.3', '142.6'],
    ['WACC=7.2%*', '51.7', '59.2', '69.7', '84.7', '108.9'],
    ['WACC=7.7%', '44.5', '50.3', '58.3', '69.5', '86.2'],
    ['WACC=8.2%', '38.6', '43.2', '49.4', '58.0', '70.3'],
]
# Mark base case with star or bold the cell
```

## Known Deprecation Warnings (fpdf2 2.8.x — safe)

| Warning | Replacement | Impact |
|---------|-------------|--------|
| `ln=1` deprecated | Use `new_x=XPos.LMARGIN, new_y=YPos.NEXT` | Code still works |
| `ln=0` deprecated | Use `new_x=XPos.RIGHT, new_y=YPos.TOP` | Code still works |
| `uni=True` deprecated (add_font) | Remove the parameter | No change |
| `split_only=True` deprecated | Use `dry_run=True, output="LINES"` | Split_only still works |

## Page Layout Constants (A4 portrait)

| Constant | Value | 
|----------|-------|
| Page width | 210mm |
| Page height | 297mm |
| Left margin (default) | 10mm |
| Right margin (default) | 10mm |
| Content width (w=0) | 190mm (page - l_margin - r_margin) |
| Usable before page break | ~270mm (page - 20mm bottom margin) |
| Auto page break margin | 20mm (recommended) |

## Minimal Working Example

```python
from fpdf import FPDF

pdf = FPDF('P', 'mm', 'A4')
pdf.set_auto_page_break(True, 20)
pdf.add_font('CJK', '', '/System/Library/Fonts/Hiragino Sans GB.ttc')
pdf.add_font('CJK', 'B', '/System/Library/Fonts/Hiragino Sans GB.ttc')

pdf.add_page()
pdf.set_font('CJK', 'B', 15)
pdf.cell(0, 10, '长鑫科技（688825）估值研究报告', new_x='LMARGIN', new_y='NEXT', align='C')
pdf.set_font('CJK', '', 9.5)
pdf.multi_cell(0, 5, '这是一段中文测试文本。通过使用Hiragino Sans GB字体，fpdf2可以正确渲染中文字符。')

pdf.output('/tmp/test.pdf')
print('OK')
```

## Delivery validation with pikepdf

```bash
python3 -c "import pikepdf; pdf=pikepdf.open('/path/to/report.pdf'); print(f'{len(pdf.pages)} pages, valid')"
```
