# -*- coding: utf-8 -*-
import io
from pptx import Presentation
from pptx.util import Emu
TPL = r'E:\PPT\S21课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\4.13款可编辑Sci技术路线，研究流程图\13款可编辑Sci技术路线，研究流程图\可编辑Sci技术路线，研究流程图.pptx'
prs = Presentation(TPL)
slides = list(prs.slides)
out = io.open(r'E:\\RSI‑EdgeVision：基于 RDK X5 的遥感地物智能解析系统\\技术路线图\\_work\\probe_out.txt', 'w', encoding='utf-8')
for idx in (11, 9):
    s = slides[idx]
    out.write('==== slide %d shapes %d\n' % (idx, len(s.shapes)))
    for z, sh in enumerate(s.shapes):
        try:
            ft = str(sh.fill.type)
        except Exception:
            ft = 'ERR'
        rgb = ''
        try:
            if sh.fill.type == 1:
                c = sh.fill.fore_color.rgb
                rgb = '#%02X%02X%02X' % (c[0], c[1], c[2])
        except Exception:
            rgb = '?'
        t = ''
        if sh.has_text_frame:
            t = sh.text_frame.text.replace('\n', '|')[:20]
        try:
            W = Emu(sh.width).inches; H = Emu(sh.height).inches
            pos = '%.2f,%.2f %.2fx%.2f A=%.2f' % (Emu(sh.left).inches, Emu(sh.top).inches, W, H, W*H)
        except Exception:
            pos = 'n/a'
        out.write('%2d|%-12s|%-22s|%-14s|%-8s|%-30s|%s\n' % (z, sh.name, str(sh.shape_type), ft, rgb, pos, t))
out.close()
print('ok')
