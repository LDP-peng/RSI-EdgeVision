# -*- coding: utf-8 -*-
import io
from docx import Document
d = Document(r'E:\\竞赛\\全球算法精英赛（硬件）\\AI+硬件.docx')
out = io.open(r'E:\\RSI‑EdgeVision：基于 RDK X5 的遥感地物智能解析系统\\技术路线图\\_work\\docx_dump.txt', 'w', encoding='utf-8')
out.write('--- PARAGRAPHS ---\n')
for i, p in enumerate(d.paragraphs):
    t = p.text.strip()
    if t:
        out.write('[%d][%s] %s\n' % (i, p.style.name, t))
out.write('--- TABLES %d ---\n' % len(d.tables))
for ti, tb in enumerate(d.tables):
    out.write('== table %d (%dx%d)\n' % (ti, len(tb.rows), len(tb.columns)))
    for r in tb.rows:
        cells = [c.text.strip().replace('\n', ' / ') for c in r.cells]
        out.write(' | '.join(cells) + '\n')
out.close()
print('ok')
