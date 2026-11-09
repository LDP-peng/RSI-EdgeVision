# -*- coding: utf-8 -*-
import re, zipfile
from lxml import etree
from docx import Document
from docx.oxml.ns import qn

GEN = "C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/RDK X5 部署变化检测模型_带封面.docx"
SRC = "C:/Users/LDP/Desktop/RDK X5 部署变化检测模型.docx"
DST = "C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/out_final.docx"

gen = Document(GEN)
body = gen.element.body
parts = []
for child in body:
    if child.tag == qn('w:sectPr'):
        break
    parts.append(etree.tostring(child, encoding='unicode'))
    if 'w:type="page"' in parts[-1] or 'type="page"' in parts[-1]:
        break
cover_xml = ''.join(parts)
print("[cover] 段落数:", len(parts), " XML 长度:", len(cover_xml))

zin = zipfile.ZipFile(SRC)
doc_xml = zin.read('word/document.xml').decode('utf-8')
m = re.search(r'<w:body(\s[^>]*)?>', doc_xml)
print("[src] <w:body> 位置:", m.start(), "~", m.end())
new_doc = doc_xml[:m.end()] + cover_xml + doc_xml[m.end():]

zout = zipfile.ZipFile(DST, 'w', zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    data = zin.read(item.filename)
    if item.filename == 'word/document.xml':
        data = new_doc.encode('utf-8')
    zout.writestr(item, data)
zout.close()
zin.close()

za = zipfile.ZipFile(SRC); zb = zipfile.ZipFile(DST)
names = [i.filename for i in za.infolist() if not i.filename.endswith("/")]
diff = [n for n in names if za.getinfo(n).CRC != zb.getinfo(n).CRC]
print("[check] 部件总数:", len(names), " 与原件不同的部件:", diff)
d = Document(DST)
print("[check] 段落总数:", len(d.paragraphs))
print("[check] 封面首行:", d.paragraphs[1].text)

