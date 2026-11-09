# -*- coding: utf-8 -*-
import io
from pptx import Presentation
from pptx.util import Emu
OUT = r'E:\\RSI‑EdgeVision：基于 RDK X5 的遥感地物智能解析系统\\技术路线图\\RDK-X5遥感边缘智能识别终端_技术路线图（模板版式）.pptx'
prs = Presentation(OUT)
out = io.open(r'E:\\RSI‑EdgeVision：基于 RDK X5 的遥感地物智能解析系统\\技术路线图\\_work\\probe_built.txt', 'w', encoding='utf-8')
for i, s in enumerate(prs.slides, 1):
    out.write('==== output slide %d\n' % i)
    for z, sh in enumerate(s.shapes):
        t = ''
        if sh.has_text_frame:
            t = sh.text_frame.text.replace('\n', '|')
        try:
            ft = str(sh.fill.type)
        except Exception:
            ft = 'ERR'
        try:
            W = Emu(sh.width).inches; H = Emu(sh.height).inches
            pos = '%.2f,%.2f %.2fx%.2f' % (Emu(sh.left).inches, Emu(sh.top).inches, W, H)
        except Exception:
            pos = 'n/a'
        out.write('%2d|%-14s|%-20s|%-14s|%-24s|%s\n' % (z, sh.name, str(sh.shape_type), ft, pos, t))
out.close()
print('ok')
