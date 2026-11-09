# -*- coding: utf-8 -*-
import io
from pptx import Presentation
from pptx.util import Emu, Pt
TPL = r'E:\\PPT\\S21课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\\课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\\4.13款可编辑Sci技术路线，研究流程图\\13款可编辑Sci技术路线，研究流程图\\可编辑Sci技术路线，研究流程图.pptx'
prs = Presentation(TPL)
s = list(prs.slides)[12]
out = io.open(r'E:\\RSI‑EdgeVision：基于 RDK X5 的遥感地物智能解析系统\\技术路线图\\_work\\s12.txt', 'w', encoding='utf-8')
for z, sh in enumerate(s.shapes):
    L = Emu(sh.left).inches; T = Emu(sh.top).inches
    W = Emu(sh.width).inches; H = Emu(sh.height).inches
    t = ''
    sz = ''
    if sh.has_text_frame:
        p0 = sh.text_frame.paragraphs[0]
        sz = None
        if p0.runs:
            sz = p0.runs[0].font.size
        t = sh.text_frame.text.strip().replace('\n', '|')
    out.write('%2d|%-14s|%-18s|%.2f,%.2f %.2fx%.2f|%s|%s\n' % (z, sh.name, str(sh.shape_type).split(' ')[0], L, T, W, H, sz, t))
out.close()
print('ok')

