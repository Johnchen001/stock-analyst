---
name: valuation-report-generator
description: 生成专业的中文上市公司估值研究报告PDF，包含完整的行业分析、财务分析、业绩预测、三种估值方法及风险因素分析
category: productivity
---

# 估值研究报告生成技能

生成专业中文上市公司估值研究报告PDF，包含完整的分析框架和排版格式。

## 使用方法

当用户要求生成某公司的估值研究报告时，按以下步骤操作：

### 第一步：数据收集

1. **公司基本信息**：从招股说明书、公司公告获取
   - 成立时间、主营业务、经营模式（IDM/Fabless等）
   - 上市信息（板块、发行价、总股本）
   - 产品矩阵、技术路线、客户资源

2. **财务数据**：从招股书/年报获取（近3-5年）
   - 营收、净利润、毛利率、净利率
   - 总资产、总负债、经营现金流
   - 研发投入、专利数量

3. **行业数据**：从TrendForce/WSTS/IC Insights等获取
   - 市场规模、增长率、未来预测
   - 竞争格局（市场份额）
   - 行业周期位置

4. **可比公司数据**：Bloomberg/Wind/公开市场数据
   - 美光、SK海力士、三星等市盈率
   - 产能数据、市值数据

5. **当前股价**：从新浪财经等获取实时行情

### 第二步：报告写作框架

报告需包含以下七个章节：

1. **执行摘要** — 200-300字，核心观点+估值结论+风险提示
2. **宏观与行业环境分析** — 宏观经济、行业周期、竞争格局、行业壁垒
3. **公司业务与战略分析** — 公司概况、产品矩阵、核心竞争力、发展战略
4. **财务分析与会计质量评估** — 历史财务数据、盈利能力、成长性、现金流、会计风险
5. **业绩预测** — 收入预测、利润预测、现金流预测（3年）
6. **估值分析** — DCF估值（含敏感性分析）、P/E相对估值、市场份额法/单位产能法、综合结论
7. **风险因素** — 8-10个系统风险分析

### 第三步：PDF生成规范

使用 **fpdf2** 生成PDF，遵循以下规范：

**字体**：
```python
self.add_font('CJK', '', '/System/Library/Fonts/Hiragino Sans GB.ttc')
self.add_font('CJK', 'B', '/System/Library/Fonts/Hiragino Sans GB.ttc')
```

**关键参数**：
- A4纸（210x297mm）
- 四边距15mm
- 正文字号9.5pt，表头8pt，注释7.5pt
- 标题层级：h1=14pt(深蓝), h2=11.5pt(中蓝), h3=10pt

**核心方法**（每个写内容的方法开头必须 `set_x(MARGIN)` 避免崩溃）：

```python
def p(self, text):    # 正文段落（multi_cell, w=CONTENT_W, h=5.2）
def h1(self, title):  # 一级标题
def h2(self, title):  # 二级标题
def h3(self, title):  # 三级标题
def bullet(self, text, indent=8):  # 圆点列表
def note(self, text):  # 小字注释
def table(self, headers, rows, col_widths):  # 表格（带分页断表+重复表头）
def hr(self):  # 分隔线
def warn_box(self, text):  # 黄色高亮风险提示框
def kv_table(self, items):  # 键值对信息表
```

**表格实现要点**：
- `col_widths` 需和为 `CONTENT_W`（180mm），若不匹配自动缩放
- 跨页时检测 `get_y() + row_h > 275` 自动翻页+重复表头
- 隔行交替色（#F8FAFF / #FFFFFF）
- 深蓝表头（#193C82），白色字，字号8pt
- **⚠️ 填充色陷阱（2026-08-05用户反馈）**：表头用 `set_fill_color(25,60,130)` 后，数据行循环前必须显式 `set_fill_color(248,250,255)`（浅蓝），否则数据行沿用表头深蓝填充 + 黑色文字 = 深蓝底黑字看不清。跨页重复表头后同样要重置。见 pdf-report-utils 技能已修复的 table() 实现。

**分页处理**：
- `auto_page_break(True, 18)` 自动分页
- 手动分页在关键章节前加 `pdf.add_page()`
- 表格内分页 + 表头重复

### 第四步：验证

```python
python3 -c "
import pikepdf, os
with pikepdf.open(path) as pdf:
    print(f'Pages: {len(pdf.pages)}')
    print(f'Size: {os.path.getsize(path)/1024:.0f} KB')
    # 检查每页是否有内容
    for i, page in enumerate(pdf.pages):
        assert page.get('/Contents') is not None, f'Page {i+1} is empty'
"
```

### 注意事项

1. **x坐标保护**：每个写内容的方法都必须先 `set_x(MARGIN)`，否则 multi_cell 会因 x 偏移抛出 `"Not enough horizontal space"` 异常
2. **TTC字体**：Hiragino Sans GB.ttc 是 TTC 格式，fpdf2 支持但会输出 DeprecationWarning 关于 `uni` 参数，传参时不要加 `uni=True`
3. **不要用 fpdf2 废弃 API**：避免 `ln=1`（改用 `new_x=XPos.LMARGIN, new_y=YPos.NEXT`）、避免 `split_only=True`（用 `dry_run=True, output="LINES"`）
4. **表格分页**：表格每行前检测 `get_y() + row_h > 275` 自动翻页，翻页后必须重新打印表头
5. **文件保存（2026-08-01更新）**：PDF 保存到 `~/Desktop/暑假/投资分析/估值报告/`（文件名 `<公司名>估值报告_YYYYMMDD.pdf`），不再保存到桌面根目录；Markdown 源文件生成 PDF 后立即删除，不保留
6. **清理**：生成后删除临时 Python 脚本（/tmp 或工作目录下 gen_*.py）
