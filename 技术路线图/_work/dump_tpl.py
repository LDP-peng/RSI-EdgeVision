# -*- coding: utf-8 -*-
import io
from pptx import Presentation
from pptx.util import Emu
TPL = r'E:\\PPT\\S21课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\\课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\\4.13款可编辑Sci技术路线，研究流程图\\13款可编辑Sci技术路线，研究流程图\\可编辑Sci技术路线，研究流程图.pptx'
prs = Presentation(TPL)
out = io.open(r'E:\\RSI‑EdgeVision：基于 RDK X5 的遥感地物智能解析系统\\技术路线图\\_work\\tpl_dump.txt', 'w', encoding='utf-8')
out.write('slide size %.2f x %.2f in, slides=%d\n' % (Emu(prs.slide_width).inches, Emu(prs.slide_height).inches, len(prs.slides._sldIdLst)))
for i, s in enumerate(prs.slides):
    texts = []
    for sh in s.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            texts.append(sh.text_frame.text.strip().replace('\n', '/'))
    out.write('== slide %d shapes=%d :: %s\n' % (i, len(s.shapes), ' ; '.join(texts)[:300]))
    for z, sh in enumerate(s.shapes):
        try:
            W = Emu(sh.width).inches; H = Emu(sh.height).inches
            L = Emu(sh.left).inches; T = Emu(sh.top).inches
            pos = '%.2f,%.2f %.2fx%.2f' % (L, T, W, H)
        except Exception:
            pos = 'n/a'
        t = ''
        if sh.has_text_frame:
            t = sh.text_frame.text.strip().replace('\n', '|')[:28]
        try:
            ft = str(sh.fill.type)
        except Exception:
            ft = 'ERR'
        out.write('%3d %-16s %-20s %-14s %-22s %s\n' % (z, sh.name, str(sh.shape_type), ft, pos, t))
out.close()
print('ok')
