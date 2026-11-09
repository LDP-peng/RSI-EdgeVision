# -*- coding: utf-8 -*-
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.enum.dml import MSO_FILL

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'RDK-X5遥感边缘智能识别终端_技术路线图（模板版式）.pptx')

TPL = r'E:\PPT\S21课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\课题申报框架构图教学思政科研绘图技术路线图visoi流程图ppt模板\4.13款可编辑Sci技术路线，研究流程图\13款可编辑Sci技术路线，研究流程图\可编辑Sci技术路线，研究流程图.pptx'

FONT = '微软雅黑'

NAVY = dict(
    ink=RGBColor(0x22, 0x2B, 0x38),
    emph=RGBColor(0x2F, 0x54, 0x96),
    fill=RGBColor(0xE9, 0xEF, 0xF9),
    border=RGBColor(0x9F, 0xB6, 0xDA),
    arrow=RGBColor(0xB9, 0xB9, 0xB9),
    caption=RGBColor(0x1F, 0x38, 0x64),
)
GRAY = dict(
    ink=RGBColor(0x33, 0x38, 0x3C),
    emph=RGBColor(0x6B, 0x71, 0x75),
    fill=RGBColor(0xF2, 0xF3, 0xF4),
    border=RGBColor(0xC6, 0xCA, 0xCE),
    arrow=RGBColor(0xCB, 0xCF, 0xD2),
    caption=RGBColor(0x4A, 0x50, 0x55),
)
PALETTE = {5: GRAY, 3: NAVY, 12: GRAY, 9: NAVY, 7: NAVY}


def set_ea(run, name=FONT):
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn('a:ea'))
    if ea is None:
        ea = rPr.makeelement(qn('a:ea'), {})
        rPr.append(ea)
    ea.set('typeface', name)


def style_run(r, size=None, bold=None, color=None, font=FONT):
    if size is not None:
        r.font.size = Pt(size)
    if bold is not None:
        r.font.bold = bold
    if color is not None:
        r.font.color.rgb = color
    r.font.name = font
    set_ea(r, font)


def only_para(shape):
    tf = shape.text_frame
    tf.word_wrap = True
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    return tf.paragraphs[0]


def set_text(shape, text, size=None, bold=None, color=None):
    p0 = only_para(shape)
    had = bool(p0.runs)
    for r in list(p0.runs)[1:]:
        r._r.getparent().remove(r._r)
    if not p0.runs:
        p0.add_run()
    r = list(p0.runs)[0]
    r.text = text
    style_run(r, size, bold, color if color is not None else (None if had else RGBColor(0x22, 0x2B, 0x38)))


def set_text2(shape, t1, t2, size=None, bold=None):
    p0 = only_para(shape)
    had = bool(p0.runs)
    while len(p0.runs) < 2:
        p0.add_run()
    rs = list(p0.runs)
    for r in rs[2:]:
        r._r.getparent().remove(r._r)
    rs = list(p0.runs)
    for r, t in zip(rs, (t1, t2)):
        r.text = t
        style_run(r, size, bold, None if had else RGBColor(0x22, 0x2B, 0x38))


def tight(sh):
    tf = sh.text_frame
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0


def clear_extra_text(slide, keep_names):
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        if sh.name in keep_names:
            continue
        if sh.text_frame.text.strip():
            sh.text_frame.text = ''


def apply_plan(slide, by_name, plan):
    for item in plan:
        name, texts, size, bold = item[0], item[1], item[2], item[3]
        sh = by_name.get(name)
        if sh is None:
            print('  MISSING', name)
            continue
        tight(sh)
        if len(texts) == 1:
            set_text(sh, texts[0], size=size, bold=bold)
        else:
            set_text2(sh, texts[0], texts[1], size=size, bold=bold)


def drop_shapes(slide, names):
    for sh in list(slide.shapes):
        if sh.name in names:
            sh._element.getparent().remove(sh._element)


def scale_shapes(slide, x0, y0, kx, ky, tx, ty):
    for sh in list(slide.shapes):
        try:
            L = Emu(sh.left).inches
            T = Emu(sh.top).inches
            W = Emu(sh.width).inches
            H = Emu(sh.height).inches
        except Exception:
            continue
        sh.left = Inches(tx + (L - x0) * kx)
        sh.top = Inches(ty + (T - y0) * ky)
        sh.width = Inches(W * kx)
        sh.height = Inches(H * ky)


def color_all_text(sh, color):
    if not sh.has_text_frame:
        return
    for para in sh.text_frame.paragraphs:
        for r in para.runs:
            r.font.color.rgb = color
            r.font.name = FONT
            set_ea(r)


EMPHASIS = {
    3: ['矩形 22', '矩形 57', '矩形 58', '矩形 59', '矩形 60', '菱形 15'],
    12: ['矩形 10', '矩形 13', '矩形 15'],
    9: ['矩形 1', '圆角矩形 3'],
    7: ['矩形 1', '矩形 2', '矩形 3', '矩形 4', '矩形 27'],
}

HIDE = {
    3: ['圆柱形 50', '圆柱形 52', '圆柱形 53'],
    9: ['矩形 38'],
}

ARROW_PREFIX = ('下箭头', '右箭头', '左箭头', '上箭头', '燕尾', '箭头')


def restyle(slide, idx):
    pal = PALETTE[idx]
    emph = set(EMPHASIS.get(idx, []))
    hide = set(HIDE.get(idx, []))
    for sh in list(slide.shapes):
        st = str(sh.shape_type)
        try:
            ftype = sh.fill.type
        except Exception:
            ftype = None
        if st.startswith('LINE'):
            try:
                sh.line.color.rgb = pal['border']
                sh.line.width = Pt(1.0)
            except Exception:
                pass
            continue
        if st.startswith('PICTURE'):
            continue
        if sh.name.startswith(ARROW_PREFIX):
            try:
                sh.fill.solid()
                sh.fill.fore_color.rgb = pal['arrow']
                sh.line.fill.background()
            except Exception:
                pass
            continue
        is_textbox = st.startswith('TEXT_BOX')
        if is_textbox:
            try:
                sh.fill.background()
                sh.line.fill.background()
            except Exception:
                pass
            color_all_text(sh, pal['ink'])
            continue
        if sh.name in hide:
            try:
                sh.fill.background()
                sh.line.fill.background()
            except Exception:
                pass
            continue
        if sh.name in emph:
            try:
                sh.fill.solid()
                sh.fill.fore_color.rgb = pal['emph']
            except Exception:
                pass
            try:
                sh.line.color.rgb = pal['emph']
                sh.line.width = Pt(1.0)
            except Exception:
                pass
            color_all_text(sh, RGBColor(0xFF, 0xFF, 0xFF))
            continue
        if ftype in (None, MSO_FILL.BACKGROUND):
            try:
                sh.fill.background()
            except Exception:
                pass
        else:
            try:
                sh.fill.solid()
                sh.fill.fore_color.rgb = pal['fill']
            except Exception:
                pass
        try:
            sh.line.color.rgb = pal['border']
            sh.line.width = Pt(1.0)
        except Exception:
            pass
        color_all_text(sh, pal['ink'])


def add_caption(slide, text, color):
    tb = slide.shapes.add_textbox(Inches(0.34), Inches(7.03), Inches(9.32), Inches(0.34))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = text
    style_run(r, size=10.5, bold=True, color=color)
    tb.fill.background()
    tb.line.fill.background()


from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR


def add_box(slide, l, t, w, h, fill, line, rounded=True, radius=0.10):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(l), Inches(t), Inches(w), Inches(h))
    if rounded:
        try:
            shp.adjustments[0] = radius
        except Exception:
            pass
    try:
        shp.shadow.inherit = False
    except Exception:
        pass
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1.0)
    return shp


def fill_text(container, lines, size=10, color=None, align=None, gap=5, bold=False,
              mleft=0.10, mright=0.10, mtop=0.08, mbot=0.08, line_spacing=None, anchor=None):
    tf = container.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(mleft)
    tf.margin_right = Inches(mright)
    tf.margin_top = Inches(mtop)
    tf.margin_bottom = Inches(mbot)
    try:
        tf.vertical_anchor = anchor if anchor is not None else MSO_ANCHOR.TOP
    except Exception:
        pass
    first = True
    for line in lines:
        runs = [(line, bold)] if isinstance(line, str) else line
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(gap)
        if line_spacing:
            p.line_spacing = line_spacing
        if align is not None:
            p.alignment = align
        for txt, b in runs:
            r = p.add_run()
            r.text = txt
            style_run(r, size=size, bold=b, color=color)
    return tf


POLICY_TITLE = '项目背景与政策支撑'
POLICY_SUB = '国家战略布局 · 广东省区域实践 · 本项目定位'

POLICY_COLS = [
    ('国家层面', [
        [('战略定位｜', True), ('统筹建设卫星通信、导航、遥感系统，构建空天地一体、通导感算融合的综合服务体系', False)],
        [('新型基建｜', True), ('卫星互联网纳入新型基础设施建设', False)],
        [('产业规模｜', True), ('“十四五”期间卫星遥感及应用产业累计产值突破 1 万亿元', False)],
        [('在轨资源｜', True), ('截至 2025 年底，我国在轨商业遥感卫星 210 颗', False)],
        [('市场规模｜', True), ('2025 年商业遥感数据与服务约 18 亿美元，预计 2026 年突破 22 亿美元', False)],
        [('下游应用｜', True), ('整体市场规模已突破 2100 亿元', False)],
    ]),
    ('广东省层面', [
        [('省级规划｜', True), ('“十五五”规划纲要（2026.4）：系统建设空天地海一体化信息网络，部署农业遥感信息智能处理技术', False)],
        [('新赛道｜', True), ('行动规划（2026.3）：商业航天列为重点培育赛道，2035 年新赛道规模突破 10 万亿元', False)],
        [('双核多点｜', True), ('行动方案（2024—2028）：广深为核心、珠海阳江为支点，2026 年关联产业规模达 3000 亿元', False)],
        [('星座布局｜', True), ('谋划大湾区通导遥一体化低轨星座', False)],
        [('产业基础｜', True), ('2025 年 AI 核心产业规模突破 3000 亿元，约占全国 1/4，122 个大模型通过国家备案', False)],
        [('应用场景｜', True), ('无人机物流、城市治理、应急救援、海洋巡检、农林监测', False)],
    ]),
    ('本项目定位', [
        [('载体｜', True), ('国产边缘算力平台 RDK X5', False)],
        [('核心｜', True), ('轻量化遥感图像变化检测算法 + 板端定点部署技术', False)],
        [('交汇点｜', True), ('“人工智能 + 遥感”与“空天地海一体化”战略方向', False)],
    ]),
]

POLICY_CONCLUSION = [
    [('政策契合度高', True)],
    [('应用落地空间明确', True)],
    [('国产算力 · 端侧智能 · 数据不出域', False)],
]


def build_policy(slide, pal):
    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)

    tb = slide.shapes.add_textbox(Inches(0.45), Inches(0.26), Inches(9.10), Inches(0.50))
    fill_text(tb, [POLICY_TITLE], size=20, color=pal['ink'], bold=True, gap=0,
              mleft=0, mright=0, mtop=0, mbot=0)
    tb.line.fill.background()
    tb.fill.background()

    sb = slide.shapes.add_textbox(Inches(0.47), Inches(0.78), Inches(9.10), Inches(0.28))
    fill_text(sb, [POLICY_SUB], size=10.5, color=pal['emph'], gap=0,
              mleft=0, mright=0, mtop=0, mbot=0)
    sb.line.fill.background()
    sb.fill.background()

    add_box(slide, 0.45, 1.14, 9.10, 0.016, pal['border'], None, rounded=False)

    col_x = [0.45, 3.583, 6.717]
    col_w = 2.833
    for k, (head, items) in enumerate(POLICY_COLS):
        x = col_x[k]
        hb = add_box(slide, x, 1.24, col_w, 0.38, pal['emph'], None, radius=0.18)
        fill_text(hb, [head], size=12, color=RGBColor(0xFF, 0xFF, 0xFF), bold=True,
                  align=PP_ALIGN.CENTER, gap=0, mleft=0.05, mright=0.05, mtop=0.04, mbot=0.02)
        if k < 2:
            body = add_box(slide, x, 1.72, col_w, 4.80, pal['fill'], pal['border'], radius=0.03)
            fill_text(body, items, size=10, color=pal['ink'], align=PP_ALIGN.LEFT,
                      gap=7, line_spacing=1.15)
        else:
            body = add_box(slide, x, 1.72, col_w, 2.05, pal['fill'], pal['border'], radius=0.05)
            fill_text(body, items, size=10, color=pal['ink'], align=PP_ALIGN.LEFT,
                      gap=8, line_spacing=1.15)
            concl = add_box(slide, x, 3.98, col_w, 2.44, pal['emph'], None, radius=0.06)
            fill_text(concl, POLICY_CONCLUSION, size=14, color=RGBColor(0xFF, 0xFF, 0xFF),
                      bold=True, align=PP_ALIGN.CENTER, gap=12, anchor=MSO_ANCHOR.MIDDLE)


PLAN_3 = [
    ('矩形 20', ['双时相遥感影像 T1 / T2'], 9, False),
    ('矩形 21', ['LEVIR-CD 全量 2048 对'], 9, False),
    ('矩形 22', ['RTMA-Net 轻量化变化检测网络'], 11, True),
    ('矩形 7', ['共享 MobileNetV2 编码器'], 9, False),
    ('矩形 24', ['TFRM 互易时相响应融合'], 9, False),
    ('矩形 25', ['MSFM 多尺度细化 + SAttM 解码'], 9, False),
    ('矩形 26', ['PyTorch → ONNX 导出'], 9, False),
    ('矩形 28', ['hb_mapper int8 量化'], 9, False),
    ('文本框 1', ['浮点 10.2 MB'], 6.5, False),
    ('文本框 2', ['定点 3.2 MB'], 6.5, False),
    ('文本框 4', ['压缩约 68%'], 6.5, False),
    ('矩形 13', ['RDK X5 边缘开发板'], 9, False),
    ('矩形 12', ['8 核 A55 · 10 TOPS BPU'], 9, False),
    ('矩形 36', ['端侧一体化检测工作站'], 9, False),
    ('菱形 15', ['报告'], 8, False),
    ('缺角矩形 16', ['灾害评估 / 城市更新 / 国土动态监测'], 9, False),
    ('矩形 57', ['STEP1'], 9, True),
    ('矩形 58', ['STEP2'], 9, True),
    ('矩形 59', ['STEP3'], 9, True),
    ('矩形 60', ['STEP4'], 9, True),
]

# 模板第 13 页 a/b/c 三栏版式：a 纵向链路、b 三合一链路、c 双行链路
PLAN_12 = [
    ('文本框 60', ['a  硬件选型与算力平台'], 10, True),
    ('文本框 17', ['b  结构前置适配'], 10, True),
    ('文本框 18', ['c  量化编译与板端运行'], 10, True),
    ('矩形 2', ['训练主机 · RTX 4080'], 9.5, False),
    ('矩形 3', ['边缘板卡 · RDK X5'], 9.5, False),
    ('矩形 4', ['8 核 Cortex-A55'], 9.5, False),
    ('矩形 5', ['10 TOPS INT8 BPU · LPDDR4'], 9.5, False),
    ('矩形 7', ['算子集'], 7.5, False),
    ('矩形 23', ['数值格式'], 7.5, False),
    ('矩形 24', ['结构约束'], 7.5, False),
    ('矩形 9', ['结构前置适配'], 9, False),
    ('矩形 10', ['一次成型 · 避免返工'], 9.5, True),
    ('矩形 12', ['60 组真实样本校准'], 8.5, False),
    ('矩形 25', ['浮点自检交叉验证'], 8.5, False),
    ('矩形 13', ['int8 定点模型 3.2 MB'], 8.5, True),
    ('矩形 14', ['板端 int8 推理'], 8.5, False),
    ('矩形 26', ['温度/内存监控'], 8.5, False),
    ('矩形 15', ['40.91 ms / 帧 · 稳定不降频'], 9, True),
]

PLAN_9 = [
    ('矩形 1', ['端侧一体化检测工作站'], 12, True),
    ('圆角矩形 2', [''], 9, False),
    ('矩形 15', ['六通道拼接'], 7.5, False),
    ('矩形 16', ['归一化 + 随机时相交换'], 7, False),
    ('文本框 36', ['预处理'], 7, False),
    ('文本框 37', ['配置'], 7, False),
    ('文本框 6', ['数据侧'], 7.5, False),
    ('矩形 22', ['数据集选择 / 样本匹配'], 8, False),
    ('矩形 24', ['预处理'], 6.5, False),
    ('圆角矩形 9', ['实验配置 · 运行环境'], 7.5, False),
    ('文本框 32', ['解释侧'], 7.5, False),
    ('矩形 23', ['六视图联动 / 误差四色图'], 8, False),
    ('矩形 25', ['点选'], 6.5, False),
    ('圆角矩形 8', ['AI 语义解释'], 8, False),
    ('矩形 13', ['端侧推理'], 8, True),
    ('圆角矩形 3', ['int8 定点推理'], 7.5, False),
    ('圆角矩形 7', ['评估报告导出'], 7.5, False),
    ('文本框 29', ['阈值 0.5'], 6.5, False),
    ('文本框 30', ['二值化'], 6.5, False),
]

PLAN_7 = [
    ('矩形 1', ['RTMA-Net 轻量化变化检测网络', ''], 9, True),
    ('矩形 2', ['共享编码器'], 8, True),
    ('矩形 3', ['互易时相融合'], 8, True),
    ('矩形 4', ['多尺度解码'], 8, True),
    ('矩形 8', ['伪变化'], 7, False),
    ('矩形 9', ['抑制'], 7, False),
    ('矩形 10', ['TFRM'], 7.5, True),
    ('矩形 11', ['差异响应'], 6.5, False),
    ('矩形 12', ['二阶能量'], 6.5, False),
    ('矩形 14', ['路由加权'], 6.5, False),
    ('矩形 13', ['一致性'], 6.5, False),
    ('圆角矩形 17', ['伪变化抑制'], 7.5, False),
    ('矩形 18', ['共享 MobileNetV2 编码器 · 多尺度特征', ''], 8, True),
    ('圆角矩形 20', ['MSFM 多尺度细化 + SAttM 解码', ''], 7.5, True),
    ('矩形 21', ['尺度上下文聚合 + 跨尺度细节融合'], 7.5, False),
    ('矩形 22', ['侧监督'], 6.5, False),
    ('矩形 24', ['语义校准'], 6.5, False),
    ('矩形 23', ['细节融合'], 6.5, False),
    ('矩形 25', ['门控'], 6.5, False),
    ('矩形 26', ['边界保留'], 6.5, False),
    ('矩形 27', ['输出变化概率图 M ∈ [0,1]，阈值 0.5 二值化', ''], 8, True),
]

CAPTION = {
    5: '背景与政策支撑：国家战略布局 → 广东省区域实践 → 本项目定位',
    3: '总体技术路线：数据 → 算法 → 量化 → 硬件与软件 → 应用',
    12: '硬件设计路线：算力选型 → 结构前置适配 → 量化编译与板端运行',
    9: '软件技术路线：数据与配置 → 推理与可视化 → 解释与输出',
    7: '算法技术路线：共享编码器 → TFRM 互易融合 → MSFM + SAttM 解码',
}

NOTES = {
    5: '内容来源：《AI+硬件.docx》背景与政策部分，压缩为一页。',
    3: '版式来源：模板第 4 页 STEP1–STEP4 阶梯流程。内容来源：《AI+硬件.docx》。',
    12: '版式来源：模板第 13 页 a/b/c 三栏流程（原图已移除，版式整体放大铺满页面）。内容来源：《AI+硬件.docx》“硬件与边缘计算端：从浮点权重到 BPU 定点模型”。',
    9: '版式来源：模板第 10 页三支柱结构。内容来源：《AI+硬件.docx》“软件：端侧一体化检测工作站”。',
    7: '版式来源：模板第 8 页分层结构。内容来源：《AI+硬件.docx》“RTMA-Net 模型原理分析”。',
}


def main():
    prs = Presentation(TPL)
    slides = list(prs.slides)
    keep = [5, 3, 12, 9, 7]
    targets = {i: slides[i] for i in keep}
    plans = {3: PLAN_3, 12: PLAN_12, 9: PLAN_9, 7: PLAN_7}

    for i in keep:
        s = targets[i]
        by_name = {sh.name: sh for sh in s.shapes}
        if i == 5:
            build_policy(s, PALETTE[i])
            s.notes_slide.notes_text_frame.text = NOTES[i]
            continue
        if i == 3:
            apply_plan(s, by_name, plans[i])
            for nm in ['文本框 1', '文本框 2', '文本框 4']:
                shp = by_name.get(nm)
                if shp is not None:
                    shp.left = Inches(6.95)
                    shp.width = Inches(1.05)
        elif i == 12:
            drop_shapes(s, ['图片 1'])
            by_name = {sh.name: sh for sh in s.shapes}
            for nm, wid in (('文本框 60', 1.46), ('文本框 17', 1.88), ('文本框 18', 2.00)):
                shp = by_name.get(nm)
                if shp is not None:
                    shp.width = Inches(wid)
            apply_plan(s, by_name, plans[i])
            scale_shapes(s, 1.56, 3.25, 1.50, 2.00, 0.62, 0.80)
        else:
            apply_plan(s, by_name, plans[i])
        clear_extra_text(s, {it[0] for it in plans[i]})
        s.notes_slide.notes_text_frame.text = NOTES[i]

    for i in keep:
        if i == 5:
            continue
        restyle(targets[i], i)

    for i in keep:
        add_caption(targets[i], CAPTION[i], PALETTE[i]['caption'])

    xml_slides = prs.slides._sldIdLst
    items = list(xml_slides)
    for i, el in enumerate(items):
        if i not in keep:
            rid = el.get(qn('r:id'))
            prs.part.drop_rel(rid)
            xml_slides.remove(el)
    order = [items[i] for i in keep]
    for el in order:
        xml_slides.remove(el)
    for el in order:
        xml_slides.append(el)

    prs.save(OUT)
    print('saved ok')


if __name__ == '__main__':
    main()
