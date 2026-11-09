#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Markdown 转成 Word(.docx)，保留标题/表格/代码块/列表/加粗/行内代码。"""
import re, sys, os
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CN = "Microsoft YaHei"
MONO = "Consolas"

def set_style_font(doc):
    # 默认样式用中文字体
    st = doc.styles["Normal"]
    st.font.name = CN
    st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), CN)

def set_run_font(run, name=CN, size=None, bold=None, color=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    rf.set(qn("w:ascii"), name)
    rf.set(qn("w:hAnsi"), name)
    rf.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color

def add_inline(par, text, base_bold=False):
    # 解析 **bold** 与 `code`
    tokens = re.split(r'(\*\*.+?\*\*|`[^`]+`)', text)
    for t in tokens:
        if not t:
            continue
        if t.startswith("**") and t.endswith("**"):
            r = par.add_run(t[2:-2])
            set_run_font(r, CN, bold=True)
        elif t.startswith("`") and t.endswith("`"):
            r = par.add_run(t[1:-1])
            set_run_font(r, MONO, size=10.5)
        else:
            r = par.add_run(t)
            set_run_font(r, CN, bold=base_bold)

def add_code_block(doc, lines):
    for ln in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Pt(12)
        r = p.add_run(ln if ln else " ")
        set_run_font(r, MONO, size=9.5)

def shade_cell(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)

def add_table(doc, header, rows):
    tbl = doc.add_table(rows=1, cols=len(header))
    tbl.style = "Table Grid"
    tbl.alignment = 1  # center
    hdr = tbl.rows[0].cells
    for i, h in enumerate(header):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_inline(p, h, base_bold=True)
        shade_cell(hdr[i], "D9E1F2")
    for row in rows:
        cells = tbl.add_row().cells
        for i, val in enumerate(row):
            if i >= len(cells):
                break
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            add_inline(p, val)
    # 列宽
    widths = [Inches(1.3), Inches(4.7)]
    for row in tbl.rows:
        for i, c in enumerate(row.cells):
            if i < len(widths):
                c.width = widths[i]

def parse(lines):
    doc = Document()
    set_style_font(doc)
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            # 收集代码块
            block = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                block.append(lines[i].rstrip("\n"))
                i += 1
            i += 1  # 跳过结束 ```
            add_code_block(doc, block)
            continue
        if stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:]:
            # 表格块
            tbl_lines = []
            while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                tbl_lines.append(lines[i].strip())
                i += 1
            # 去分隔行
            data = [l for l in tbl_lines if not re.match(r'^\|[\s:|-]+\|$', l)]
            if data:
                cells = [c.strip() for c in data[0].strip("|").split("|")]
                rows = []
                for line in data[1:]:
                    row = [c.strip() for c in line.strip("|").split("|")]
                    rows.append(row)
                add_table(doc, cells, rows)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m and not line.startswith("```"):
            level = len(m.group(1))
            text = m.group(2)
            p = doc.add_heading(level=level)
            p.text = ""
            add_inline(p, text)
            if level == 1:
                for r in p.runs:
                    r.font.size = Pt(20)
            elif level == 2:
                for r in p.runs:
                    r.font.size = Pt(16)
            elif level == 3:
                for r in p.runs:
                    r.font.size = Pt(13.5)
            i += 1
            continue
        if stripped == "---":
            p = doc.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            pbdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:space"), "1")
            bottom.set(qn("w:color"), "999999")
            pbdr.append(bottom)
            pPr.append(pbdr)
            i += 1
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            p = doc.add_paragraph(style="List Bullet")
            p.text = ""
            add_inline(p, stripped[2:])
            i += 1
            continue
        # 有序列表，保留序号文本
        mnum = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if mnum:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            p.text = ""
            add_inline(p, mnum.group(1) + ". " + mnum.group(2))
            i += 1
            continue
        # 普通段落
        p = doc.add_paragraph()
        p.text = ""
        add_inline(p, stripped)
        i += 1
    return doc

def main():
    if len(sys.argv) < 3:
        print("usage: md2docx.py <in.md> <out.docx>")
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    doc = parse(lines)
    doc.save(dst)
    print("saved:", dst)

if __name__ == "__main__":
    main()

