# -*- coding: utf-8 -*-
import sys
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = "C:/Users/LDP/Desktop/RDK X5 部署变化检测模型.docx"
OUT = "C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/RDK X5 部署变化检测模型_带封面.docx"

CN_T = "黑体"
CN_B = "宋体"
LAT = "Times New Roman"
INK = "1B2430"
SUB = "5B6B7C"
ACCENT = "1A5FB4"

META = [
    ("项目名称", "RSI-EdgeVision · 基于 RDK X5 的遥感地物智能解析系统"),
    ("技术路线", "PyTorch → ONNX → hb_mapper 量化 → RDK X5 端侧推理"),
    ("核心算法", "REPBNet（双时相输入 x1 / x2，256×256）"),
    ("数据集", "LEVIR-CD（建筑物变化检测）"),
    ("部署平台", "RDK X5（bayes-e · int8 量化 · 4 GB）"),
    ("作　　者", "李东澎"),
    ("学　　号", ""),
    ("指导教师", "陈汉添"),
]

def sr(run, cn=CN_B, size=12, bold=False, color=None, latin=LAT, char_sp=None):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = latin
    rPr = run._element.get_or_add_rPr()
    rf = rPr.get_or_add_rFonts()
    rf.set(qn('w:eastAsia'), cn)
    rf.set(qn('w:ascii'), latin)
    rf.set(qn('w:hAnsi'), latin)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    if char_sp:
        sp = OxmlElement('w:spacing')
        sp.set(qn('w:val'), str(int(char_sp * 20)))
        rPr.append(sp)
    return run

def P(doc, text="", align="center", before=0, after=0, line=None):
    p = doc.add_paragraph()
    p.alignment = {"center": WD_ALIGN_PARAGRAPH.CENTER,
                   "left": WD_ALIGN_PARAGRAPH.LEFT,
                   "right": WD_ALIGN_PARAGRAPH.RIGHT}[align]
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if line:
        pf.line_spacing = line
    if text:
        sr(p.add_run(text))
    return p

def hrule(doc, color="C9D3DE", sz=6, inset_cm=5.15):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.left_indent = Cm(inset_cm)
    pf.right_indent = Cm(inset_cm)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    b = OxmlElement('w:bottom')
    b.set(qn('w:val'), 'single')
    b.set(qn('w:sz'), str(sz))
    b.set(qn('w:space'), '1')
    b.set(qn('w:color'), color)
    pbdr.append(b)
    pPr.append(pbdr)
    return p

def top_rule(doc, color_start="1A5FB4", color_end="C9D9EA", sz=14):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    b = OxmlElement('w:bottom')
    b.set(qn('w:val'), 'single')
    b.set(qn('w:sz'), str(sz))
    b.set(qn('w:space'), '0')
    b.set(qn('w:color'), color_start)
    pbdr.append(b)
    pPr.append(pbdr)
    return p

def no_border_table(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideV'):
        el = OxmlElement('w:' + edge)
        el.set(qn('w:val'), 'none')
        el.set(qn('w:sz'), '0')
        el.set(qn('w:space'), '0')
        borders.append(el)
    ih = OxmlElement('w:insideH')
    ih.set(qn('w:val'), 'single')
    ih.set(qn('w:sz'), '4')
    ih.set(qn('w:space'), '0')
    ih.set(qn('w:color'), 'EEF2F6')
    borders.append(ih)
    tblPr.append(borders)

def build_cover(doc):
    top_rule(doc)
    P(doc, "广州软件学院", before=20, after=0).runs[0].font.size = Pt(15)
    sr(doc.paragraphs[-1].runs[0], cn=CN_B, size=15, color=SUB, char_sp=6)

    for _ in range(6):
        P(doc)

    t1 = P(doc, line=1.4)
    sr(t1.add_run("REPBNet 变化检测算法"), cn=CN_T, size=22, bold=True, color=INK)
    t2 = P(doc, line=1.45)
    sr(t2.add_run("× RDK X5 端侧部署"), cn=CN_T, size=22, bold=True, color=INK)

    s = P(doc, before=14)
    sr(s.add_run("— 算法 × 芯片：从 PyTorch 到地平线 BPU 的完整落地链路 —"), cn=CN_B, size=12, color=SUB)

    P(doc, before=6)
    hrule(doc, inset_cm=5.15)

    for _ in range(2):
        P(doc)

    table = doc.add_table(rows=0, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    no_border_table(table)
    for k, v in META:
        row = table.add_row()
        c0, c1 = row.cells
        c0.width = Cm(3.0)
        c1.width = Cm(11.2)
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_before = Pt(5)
        p0.paragraph_format.space_after = Pt(5)
        sr(p0.add_run(k), cn=CN_B, size=12, color=SUB, char_sp=2)
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_before = Pt(5)
        p1.paragraph_format.space_after = Pt(5)
        if v:
            sr(p1.add_run(v), cn=CN_B, size=12, color=INK)

    for _ in range(7):
        P(doc)

    d = P(doc)
    sr(d.add_run("2026 年 9 月"), cn=CN_B, size=14, color=SUB, char_sp=3)

    pb = doc.add_paragraph()
    pb.add_run().add_break(WD_BREAK.PAGE)

target = Document(SRC)
print("[src] 页面: %.2f x %.2f cm" % (target.sections[0].page_width.cm, target.sections[0].page_height.cm))
print("[src] 段落数:", len(target.paragraphs))

cover = Document()
build_cover(cover)

body = target.element.body
sectPr = body.find(qn('w:sectPr'))
idx = 0
for el in list(cover.element.body):
    if el.tag == qn('w:sectPr'):
        continue
    body.insert(idx, el)
    idx += 1

target.save(OUT)
print("[out] 已保存:", OUT)
print("[out] 现在段落数:", len(Document(OUT).paragraphs))

print("---- 封面结构校验 ----")
d2 = Document(OUT)
for i, par in enumerate(d2.paragraphs[:26]):
    t = par.text.strip()
    if not t:
        continue
    r = par.runs[0]
    ea = r._element.rPr.rFonts.get(qn('w:eastAsia')) if r._element.rPr is not None and r._element.rPr.rFonts is not None else None
    print("%2d | %-8s | %-5s | %s" % (i, ea, (str(r.font.size.pt) if r.font.size else "-"), t[:52]))
print("---- 表格 ----")
for row in d2.tables[0].rows:
    print("   %s : %s" % (row.cells[0].text.strip(), row.cells[1].text.strip()))
print("---- 分页符 ----")
for i, par in enumerate(d2.paragraphs):
    if 'w:br' in par._p.xml and 'type="page"' in par._p.xml:
        print("   page break at paragraph index", i)
        break
