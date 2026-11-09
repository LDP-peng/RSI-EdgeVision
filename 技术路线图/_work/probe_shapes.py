# -*- coding: utf-8 -*-
from pptx import Presentation
from pptx.util import Emu
TPL = r'E:\PPT\S21课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\4.13款可编辑Sci技术路线，研究流程图\13款可编辑Sci技术路线，研究流程图\可编辑Sci技术路线，研究流程图.pptx'
prs = Presentation(TPL)
slides = list(prs.slides)
for idx in (3, 11, 9, 7):
    s = slides[idx]
    print('==== slide', idx, 'shapes', len(s.shapes))
    for z, sh in enumerate(s.shapes):
        try:
            ft = sh.fill.type
        except Exception as e:
            ft = 'ERR'
        t = ''
        if sh.has_text_frame:
            t = sh.text_frame.text.replace('\n', '|')[:22]
        try:
            pos = '%.1f,%.1f %.1fx%.1f' % (Emu(sh.left).inches, Emu(sh.top).inches, Emu(sh.width).inches, Emu(sh.height).inches)
        except Exception:
            pos = 'n/a'
        print('%2d %-12s %-24s %-10s %-24s %s' % (z, sh.name, str(sh.shape_type), str(ft), pos, t))
