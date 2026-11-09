#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report.py - 生成 HTML 格式的双时相遥感变化检测评估报告。

报告样式对齐参赛参考件：标题栏 + 四张概览卡片 + 分节标题(左侧蓝条) + 指标表格 + 样本可视化网格。
输出为单文件 HTML（图片以 base64 内嵌），可直接拷走用于比赛展示、实验总结与结果归档。

用法（板子 ~/deploy 下）：
    /usr/bin/python3 report.py
    /usr/bin/python3 report.py --data demo --thresh 0.5
    /usr/bin/python3 report.py --eval eval_results_test.csv --dataset "LEVIR-CD(test)"
    /usr/bin/python3 report.py --eval eval_results_test.csv eval_results_uav.csv --ai

数据来源：
    --eval 指向 batch_eval.py 产出的逐样本 CSV（可给多个，每个 CSV 汇总成表格一行）；
    不传时自动扫描本目录下的 eval_results*.csv；
    仍无数据时只生成"样本可视化 + 结果分析"，指标表标注为待评估。
"""
import os
import sys
import csv
import glob
import base64
import argparse
from datetime import datetime
from html import escape

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

SIZE = 256
DEFAULT_THRESH = 0.5


# ------------------------------------------------------------------ 指标计算
def safe_ratio(num, den):
    return float(num) / float(den) if den else 0.0


def kappa(tp, fp, fn, tn):
    """由混淆矩阵计算 Kappa 系数。"""
    n = tp + fp + fn + tn
    if n == 0:
        return 0.0
    po = float(tp + tn) / n
    pe = (float((tp + fp) * (tp + fn)) + float((fn + tn) * (fp + tn))) / (n * n)
    if abs(1.0 - pe) < 1e-12:
        return 0.0
    return (po - pe) / (1.0 - pe)


def read_eval_csv(path):
    """读取 batch_eval.py 的逐样本 CSV，返回 (逐样本行, 混淆矩阵汇总)。"""
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for rec in csv.DictReader(f):
            try:
                rows.append({
                    "name": rec["name"],
                    "precision": float(rec["precision"]),
                    "recall": float(rec["recall"]),
                    "f1": float(rec["f1"]),
                    "iou": float(rec["iou"]),
                    "tp": int(float(rec["tp"])),
                    "fp": int(float(rec["fp"])),
                    "fn": int(float(rec["fn"])),
                    "tn": int(float(rec["tn"])),
                })
            except (KeyError, ValueError, TypeError):
                continue
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    tn = sum(r["tn"] for r in rows)
    prec = safe_ratio(tp, tp + fp)
    rec = safe_ratio(tp, tp + fn)
    agg = {
        "precision": prec,
        "recall": rec,
        "f1": safe_ratio(2 * prec * rec, prec + rec),
        "iou": safe_ratio(tp, tp + fp + fn),
        "kappa": kappa(tp, fp, fn, tn),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "n": len(rows),
    }
    return rows, agg


def dataset_label(csv_path=None, override=None, fallback=""):
    """由 CSV 文件名推断数据集名，如 eval_results_test.csv -> test。"""
    if override:
        return override
    if not csv_path:
        return fallback or "-"
    base = os.path.basename(csv_path)
    if base.lower().endswith(".csv"):
        base = base[:-4]
    for pfx in ("eval_results_", "eval_results", "eval_"):
        if base.startswith(pfx):
            base = base[len(pfx):]
            break
    return base.strip("_-") or fallback or "-"


def pick_samples(rows, count):
    """按 F1 排序挑典型样本：最优 / 中位 / 最差。"""
    if not rows or count <= 0:
        return []
    ordered = sorted(rows, key=lambda r: r["f1"], reverse=True)
    picked, seen = [], set()

    def take(idx, tag):
        idx = max(0, min(idx, len(ordered) - 1))
        row = ordered[idx]
        if row["name"] in seen:
            return
        seen.add(row["name"])
        picked.append({"row": row, "tag": tag})

    if count == 1:
        take(0, "最优样本")
    elif count == 2:
        take(0, "最优样本")
        take(len(ordered) - 1, "最差样本")
    else:
        take(0, "最优样本")
        take(len(ordered) // 2, "中位样本")
        take(len(ordered) - 1, "最差样本")

    i = 1
    while len(picked) < count and i < len(ordered):
        take(i, "样本")
        i += 1
    return picked


# ------------------------------------------------------------------ 图像处理
def im_data_url(bgr, ext=".jpg", quality=85):
    """BGR 图 -> data URI（base64 内嵌）。"""
    import cv2
    if bgr is None:
        return ""
    params = [cv2.IMWRITE_JPEG_QUALITY, quality] if ext == ".jpg" else []
    ok, buf = cv2.imencode(ext, bgr, params)
    if not ok:
        return ""
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return "data:%s;base64,%s" % (mime, base64.b64encode(buf).decode("utf-8"))


def img_ref(bgr, src_path, embed=True, ext=".jpg", quality=85):
    """按需返回 base64 内嵌或本地文件引用。"""
    if bgr is None:
        return ""
    if embed:
        return im_data_url(bgr, ext, quality)
    return "file:///" + os.path.abspath(src_path).replace(os.sep, "/")


def make_error_map(pred, gt):
    """误差分析图：TP 绿 / FP 红 / FN 黄 / TN 暗青绿（与界面同配色，BGR）。"""
    import numpy as np
    h, w = gt.shape
    img = np.zeros((h, w, 3), np.uint8)
    img[:, :] = (42, 58, 40)
    img[gt & ~pred] = (40, 128, 175)
    img[pred & ~gt] = (48, 44, 152)
    img[pred & gt] = (58, 120, 48)
    return img


def build_sample(engine, data_dir, name, tag, row, thresh=0.5, embed=True):
    """跑一次推理，产出报告需要的 7 张图与统计文字。"""
    import cv2
    import numpy as np

    a_path = os.path.join(data_dir, "A", name)
    b_path = os.path.join(data_dir, "B", name)
    l_path = os.path.join(data_dir, "label", name)

    a_bgr, b_bgr, x1, x2 = engine.preprocess(a_path, b_path)
    prob = engine._mock_predict(a_bgr, b_bgr) if engine.mock else engine._real_predict(x1, x2)
    mask = (prob > thresh).astype(np.uint8) * 255
    overlay = b_bgr.copy()
    overlay[mask > 0] = (0, 0, 255)
    heat = cv2.applyColorMap((np.clip(prob, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)

    gt_bgr = None
    err_bgr = None
    if os.path.exists(l_path):
        gt = cv2.imread(l_path, cv2.IMREAD_GRAYSCALE)
        if gt is not None:
            if gt.shape[:2] != mask.shape:
                gt = cv2.resize(gt, (mask.shape[1], mask.shape[0]))
            gt_bin = gt > 127
            gt_bgr = cv2.cvtColor((gt_bin.astype(np.uint8) * 255), cv2.COLOR_GRAY2BGR)
            err_bgr = make_error_map(mask > 0, gt_bin)

    ratio = float((mask > 0).mean())
    return {
        "name": name,
        "tag": tag,
        "f1": row.get("f1") if row else None,
        "iou": row.get("iou") if row else None,
        "thresh": thresh,
        "ratio": ratio,
        "mock": bool(engine.mock),
        "t1": img_ref(a_bgr, a_path, embed),
        "t2": img_ref(b_bgr, b_path, embed),
        "gt": img_ref(gt_bgr, l_path, embed),
        "mask": img_ref(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR), a_path, embed, ext=".png"),
        "heat": img_ref(heat, a_path, embed),
        "overlay": img_ref(overlay, a_path, embed),
        "err": img_ref(err_bgr, l_path, embed, ext=".png"),
    }


# ------------------------------------------------------------------ HTML 样式
CSS = """
    body { margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; color: #111111; background: #ffffff; }
    header { padding: 18px 24px; background: #ffffff; color: #111111; border-bottom: 2px solid #1f2937; }
    main { max-width: 1380px; margin: 0 auto; padding: 18px 18px 24px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    h2 { margin-top: 28px; border-left: 5px solid #2563eb; padding-left: 10px; font-size: 20px; color: #111111; }
    h3 { margin: 0; font-size: 16px; }
    p, li { line-height: 1.75; }
    .meta { color: #374151; }
    .summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
    .card, .textbox { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; }
    .card b { display: block; font-size: 22px; color: #111111; margin-bottom: 4px; }
    .textbox { white-space: normal; }
    table { width: 100%; border-collapse: collapse; background: #ffffff; border: 1px solid #cbd5e1; }
    th, td { padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: 12px; color: #111111; }
    th { background: #eff6ff; color: #111111; }
    .grid { display: grid; gap: 10px; }
    .grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); align-items: start; }
    figure { margin: 0; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; }
    figcaption { margin-top: 6px; color: #111111; font-size: 11px; text-align: center; line-height: 1.3; }
    img { width: 100%; height: 150px; object-fit: contain; background: #f8fafc; border-radius: 4px; }
    .placeholder, .empty { display: grid; place-items: center; min-height: 150px; color: #475569; background: #f8fafc; border-radius: 5px; font-size: 12px; }
    .sample { margin-top: 16px; }
    .sample-head { display: flex; align-items: center; gap: 10px; margin: 18px 0 10px; flex-wrap: wrap; }
    .badge { background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; border-radius: 999px; padding: 2px 10px; font-size: 11px; }
    .badge2 { color: #374151; font-size: 11px; }
    .legend { margin-top: 8px; display: flex; gap: 16px; flex-wrap: wrap; color: #374151; font-size: 11px; }
    .legend i { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 5px; vertical-align: -2px; }
    .tips { margin: 0; padding-left: 20px; }
    .metric-note { margin-top: 10px; color: #111111; }
    .warn { margin: 0 0 14px; padding: 12px 16px; border: 1px solid #f0c8c8; border-left: 5px solid #d14343; background: #fff7f7; color: #8a1f1f; border-radius: 6px; font-size: 13px; }
    .foot { margin-top: 24px; color: #6b7280; font-size: 11px; text-align: center; }
    @media print {
      body { background: white; color: #111111; }
      main { padding: 8px; }
      .card, .textbox, table, figure { break-inside: avoid; }
    }
"""

ERROR_LEGEND = """
      <div class="legend">
        <span><i style="background:#30783A"></i>TP 正确变化</span>
        <span><i style="background:#982C30"></i>FP 误报</span>
        <span><i style="background:#AF8028"></i>FN 漏检</span>
        <span><i style="background:#283A2A"></i>TN 正确负例</span>
      </div>
"""


# ------------------------------------------------------------------ HTML 组装
def _num(value, digits=4):
    if value is None:
        return "-"
    try:
        return ("%." + str(digits) + "f") % float(value)
    except (TypeError, ValueError):
        return escape(str(value))


def _fig(caption, url):
    if not url:
        return '<figure><div class="placeholder">无图像</div><figcaption>%s</figcaption></figure>' % escape(caption)
    return '<figure><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>' % (
        url, escape(caption), escape(caption))


def _sample_section(sample, index):
    fig_list = [
        ("T1 前时相影像", sample["t1"]),
        ("T2 后时相影像", sample["t2"]),
        ("Ground Truth", sample["gt"]),
        ("预测二值变化图", sample["mask"]),
        ("概率热力图", sample["heat"]),
        ("叠加图", sample["overlay"]),
        ("误差分析图", sample["err"]),
    ]
    figs = "\n".join(_fig(c, u) for c, u in fig_list)
    metric_note = ""
    if sample.get("f1") is not None:
        metric_note = "F1 %s ｜ IoU %s" % (_num(sample["f1"]), _num(sample["iou"]))
    src_note = "模拟推理（未加载板端模型）" if sample.get("mock") else "板端 BPU 实机推理"
    return """
    <section class="sample">
      <div class="sample-head">
        <h3>样本 %d：%s</h3>
        <span class="badge">%s</span>
        <span class="badge2">%s ｜ 变化像素占比 %.2f%% ｜ %s</span>
      </div>
      <div class="grid grid-4">
%s
      </div>
%s
    </section>
""" % (index, escape(sample["name"]), escape(sample["tag"]), metric_note,
       sample["ratio"] * 100.0, src_note, figs,
       ERROR_LEGEND if sample["err"] else "")


def build_analysis(metrics, samples, thresh):
    """由真实指标自动生成"结果分析"文字（不依赖任何模型接口）。"""
    if not metrics:
        return "<p>当前未检测到可汇总的评估指标，请先运行 batch_eval.py 生成逐样本 CSV 后再生成报告。</p>"
    best = max(metrics, key=lambda m: m["f1"])
    lines = []
    lines.append(
        "<p><b>整体表现：</b>本次评估覆盖 <b>%d</b> 对双时相影像，整体 Precision %.4f、Recall %.4f、"
        "F1 %.4f、IoU %.4f、Kappa %.4f。</p>"
        % (best["n"], best["precision"], best["recall"], best["f1"], best["iou"], best["kappa"])
    )
    gap = best["precision"] - best["recall"]
    if abs(gap) < 0.03:
        balance = "精确率与召回率基本平衡，漏检与误报处于同一量级。"
    elif gap > 0:
        balance = "精确率高于召回率，主要误差来自误报；若场景更看重“少报错”，可适当提高判别阈值。"
    else:
        balance = "召回率高于精确率，主要误差来自漏检；若场景更看重“不漏检”，可适当降低判别阈值。"
    lines.append("<p><b>误差倾向：</b>%s 当前阈值取 %.2f。</p>" % (balance, thresh))

    detail = ""
    for sample in samples:
        if sample.get("f1") is not None and sample["tag"] in ("最差样本", "中位样本"):
            detail = ("<p><b>典型样本：</b>报告纳入的最差样本 %s（F1 %s）反映当前困难场景的检出水平，"
                      "其变化像素占比为 %.2f%%，可作为后续阈值调优与样本补强的参考。</p>"
                      % (escape(sample["name"]), _num(sample["f1"]), sample["ratio"] * 100.0))
            break
    if detail:
        lines.append(detail)

    if len(metrics) > 1:
        lines.append("<p><b>数据集对比：</b>%s。%s 表现最优（F1 %s）。</p>"
                     % ("；".join("%s F1 %s" % (escape(m["dataset"]), _num(m["f1"])) for m in metrics),
                        escape(best["dataset"]), _num(best["f1"])))
    return "\n".join(lines)


def build_conclusion(metrics, samples):
    if not metrics:
        return ("<p>系统已打通“数据准备 - 板端推理 - 指标评估 - 可视化 - 报告导出”的完整链路，"
                "补齐评估数据后即可形成定量结论。</p>")
    best = max(metrics, key=lambda m: m["f1"])
    parts = []
    parts.append("<p>基于 %s 的评估结果显示，REPB-Net 在 int8 定点化后端到端 F1 为 <b>%s</b>，"
                 "IoU 为 <b>%s</b>，Kappa 为 %s，说明模型在压缩至 3.2 MB 后仍保持了可用的检测精度。</p>"
                 % (escape(best["dataset"]), _num(best["f1"]), _num(best["iou"]), _num(best["kappa"])))
    if samples:
        parts.append("<p>报告的 %d 组典型样本覆盖了最优、中位与最差表现，配合四色误差分析图，"
                     "可直观定位误报与漏检区域，为阈值调优和后续样本补强提供依据。</p>" % len(samples))
    parts.append("<p>综上，本作品已形成“数据管理 - 模型训练/量化 - 边缘推理 - 指标评估 - 可视化解释 - 报告导出”"
                 "的完整闭环，可支撑灾害评估、城市更新监管与国土动态监测等应用场景。</p>")
    return "\n".join(parts)


def build_html(dataset, metrics, samples, device_rows, analysis, conclusion, extra_note=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_n = sum(m["n"] for m in metrics) if metrics else 0

    if metrics:
        metric_rows = "\n".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (escape(m["dataset"]), escape(m["method"]), _num(m["f1"]), _num(m["iou"]),
               _num(m["kappa"]), _num(m["recall"]), _num(m["precision"]))
            for m in metrics)
        best = max(metrics, key=lambda m: m["f1"])
        best_row = ("%s，F1 = %s，IoU = %s" % (escape(best["dataset"]), _num(best["f1"]), _num(best["iou"])))
        datasets = " / ".join(dict.fromkeys(m["dataset"] for m in metrics))
        methods = " / ".join(dict.fromkeys(m["method"] for m in metrics))
        eval_desc = ("本节汇总当前数据集下的主实验评估结果，包含 F1、IoU、Kappa、Recall、Precision 等核心指标，"
                     "用于衡量 REPB-Net 经 int8 量化后在 RDK X5 上的实际检测性能。")
    else:
        metric_rows = '<tr><td>-</td><td>-</td><td>待评估</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>'
        best_row = "待评估"
        datasets = dataset
        methods = "REPB-Net"
        eval_desc = "尚未检测到 batch_eval.py 输出的评估数据，本节暂以占位行展示，补齐 CSV 后重新生成报告即可。"

    warn_html = ""
    if any(s.get("mock") for s in samples):
        warn_html = ('<div class="warn">本报告基于<b>模拟推理</b>生成（当前环境未检测到 hbm_runtime），指标与可视化结果<b>不代表真实模型</b>，仅供版式预览与流程联调使用，请勿用于正式评估或比赛展示。</div>')

    sample_blocks = "\n".join(_sample_section(s, i) for i, s in enumerate(samples, 1))
    if not sample_blocks:
        sample_blocks = '<div class="empty">当前未找到可用于报告展示的变化检测样本。</div>'

    device_html = "\n".join("<tr><td>%s</td><td>%s</td></tr>" % (escape(k), escape(str(v)))
                            for k, v in device_rows)

    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>双时相遥感变化检测评估报告</title>
  <style>%s</style>
</head>
<body>
  <header>
    <h1>双时相遥感变化检测评估报告</h1>
    <div class="meta">生成时间：%s ｜ 数据集：%s ｜ 部署平台：RDK X5（4 GB / BPU int8）｜ 核心模型：REPB-Net</div>
  </header>
  <main>
    %s
    <section class="summary">
      <div class="card"><b>%s</b>当前分析数据集</div>
      <div class="card"><b>%d</b>评估样本（对）</div>
      <div class="card"><b>%d</b>主实验指标条目</div>
      <div class="card"><b>%d</b>典型样本写入报告</div>
    </section>

    <h2>一、报告说明</h2>
    <div class="textbox">
      <p>本报告面向双时相遥感变化检测任务，汇总当前数据集下的主实验指标、典型变化检测结果与可视化解释内容，并在边缘端 RDK X5 上完成推理与结果归档。报告可用于比赛展示、实验总结、项目验收或阶段性评估。</p>
      <ul class="tips">
        <li>评估数据部分汇总 F1、IoU、Kappa、Recall、Precision 等核心指标。</li>
        <li>变化检测部分展示前时相、后时相、Ground Truth 与 REPB-Net 的二值图、热力图与叠加图。</li>
        <li>误差分析图采用 TP / FP / FN / TN 四色标注，用于定位误报与漏检。</li>
      </ul>
      %s
    </div>

    <h2>二、评估数据</h2>
    <div class="textbox">
      <p><b>实验数据说明：</b>%s</p>
      <p class="metric-note"><b>覆盖数据集：</b>%s；<b>已纳入方法：</b>%s</p>
      <p class="metric-note"><b>最优结果：</b>%s</p>
    </div>
    <table>
      <thead><tr><th>数据集</th><th>方法</th><th>F1</th><th>IoU</th><th>Kappa</th><th>Recall</th><th>Precision</th></tr></thead>
      <tbody>%s</tbody>
    </table>

    <h2>三、变化检测与误差分析可视化</h2>
    %s

    <h2>四、结果分析与评价</h2>
    <div class="textbox">%s</div>

    <h2>五、部署与运行信息</h2>
    <table>
      <thead><tr><th>项目</th><th>取值</th></tr></thead>
      <tbody>%s</tbody>
    </table>

    <h2>六、综合结论</h2>
    <div class="textbox">%s</div>

    <div class="foot">RSI-EdgeVision ｜ 基于 RDK X5 的遥感地物智能解析系统 ｜ 报告由 report.py 自动生成</div>
  </main>
</body>
</html>
""" % (CSS, escape(now), escape(dataset), warn_html, escape(dataset), total_n, len(metrics), len(samples),
       extra_note and ("<p>%s</p>" % escape(extra_note)) or "",
       eval_desc, escape(datasets), escape(methods), best_row, metric_rows,
       sample_blocks, analysis, device_html, conclusion)


# ------------------------------------------------------------------ 主流程
def device_table(bin_path, engine):
    rows = []
    size_txt = "-"
    if bin_path and os.path.exists(bin_path):
        n = os.path.getsize(bin_path)
        size_txt = "%s 字节（%.1f MB，int8 定点）" % ("{:,}".format(n), n / 1024.0 / 1024.0)
    rows.append(("部署平台", "RDK X5（4 GB 内存 / 无独立 GPU / BPU int8 加速）"))
    rows.append(("量化模型", "%s ｜ %s" % (os.path.basename(bin_path) if bin_path else "repbnet_cd.bin", size_txt)))
    rows.append(("浮点权重", "best_model.pth（2,477,892 参数 / 约 10.2 MB），较量化模型压缩约 68%"))
    rows.append(("工具链", "hb_mapper 1.24.3 ｜ march bayes-e ｜ ONNX opset 11"))
    rows.append(("输入 / 输出", "x1、x2 各 1x3x256x256；输出 change_map 256x256（变化概率图）"))
    rows.append(("预处理", "BGR 拼 6 通道 → /255 → 减均值 → 除标准差 → BGR 转 RGB → HWC 转 CHW"))
    if engine is not None:
        rows.append(("推理方式", "模拟推理（未检测到 hbm_runtime，结果不代表真实模型）" if engine.mock
                     else "板端 BPU 实机推理（hbm_runtime 加载 .bin）"))
    return rows


def main():
    ap = argparse.ArgumentParser(description="生成 HTML 格式的双时相遥感变化检测评估报告")
    ap.add_argument("--data", default=os.path.join(APP_DIR, "demo"), help="含 A/B/label 的数据目录")
    ap.add_argument("--bin", default=None, help="量化模型 .bin 路径（默认自动查找）")
    ap.add_argument("--eval", nargs="*", default=None, help="batch_eval.py 产出的 CSV，可给多个")
    ap.add_argument("--dataset", default=None, help="数据集名称（默认由 CSV 文件名推断）")
    ap.add_argument("--samples", type=int, default=3, help="写入报告的典型样本数量，默认 3")
    ap.add_argument("--thresh", type=float, default=DEFAULT_THRESH, help="二值化阈值，默认 0.5")
    ap.add_argument("--ai", action="store_true", help="调用通义千问为最优样本生成语义解释")
    ap.add_argument("--out", default=os.path.join(APP_DIR, "report.html"), help="输出 HTML 路径")
    ap.add_argument("--no-embed", action="store_true", help="图片改为文件引用（默认 base64 内嵌）")
    args = ap.parse_args()

    data_dir = os.path.abspath(args.data)
    embed = not args.no_embed

    # 1) 收集评估 CSV
    csv_paths = [os.path.abspath(p) for p in (args.eval or []) if os.path.exists(p)]
    if not csv_paths:
        csv_paths = sorted(glob.glob(os.path.join(APP_DIR, "eval_results*.csv")))
        if csv_paths:
            print("[eval] 未指定 --eval，自动使用: %s" % ", ".join(os.path.basename(p) for p in csv_paths))

    dataset = dataset_label(csv_paths[0] if csv_paths else None, args.dataset, os.path.basename(data_dir))
    metrics, sample_seeds, total_rows = [], [], 0
    for idx, path in enumerate(csv_paths):
        try:
            rows, agg = read_eval_csv(path)
        except Exception as exc:
            print("[warn] 读取失败 %s: %s" % (path, exc))
            continue
        if not rows:
            continue
        label = dataset if idx == 0 else dataset_label(path, None, dataset)
        metrics.append({
            "dataset": label, "method": "REPB-Net（int8 / BPU）", "n": agg["n"],
            "f1": agg["f1"], "iou": agg["iou"], "kappa": agg["kappa"],
            "recall": agg["recall"], "precision": agg["precision"],
            "tp": agg["tp"], "fp": agg["fp"], "fn": agg["fn"], "tn": agg["tn"],
        })
        total_rows += agg["n"]
        if idx == 0:
            sample_seeds = pick_samples(rows, args.samples)
        print("[eval] %s -> %d 对，F1=%.4f IoU=%.4f" % (os.path.basename(path), agg["n"], agg["f1"], agg["iou"]))

    # 2) 加载模型 + 渲染典型样本
    engine = None
    samples = []
    if args.samples > 0 and os.path.isdir(os.path.join(data_dir, "A")):
        try:
            from infer import InferEngine
            engine = InferEngine(args.bin)
            if engine.mock:
                print("[infer] 未检测到 hbm_runtime，进入模拟推理模式（仅用于预览报告样式）")
        except Exception as exc:
            print("[warn] 模型加载失败，跳过样本可视化: %s" % exc)

        if engine is not None:
            if not sample_seeds:
                names = sorted(os.listdir(os.path.join(data_dir, "A")))[:args.samples]
                sample_seeds = [{"row": None, "tag": "样本"} for _ in names]
                sample_seeds = [dict(seed, name=n) for seed, n in zip(sample_seeds, names)]
            for seed in sample_seeds:
                name = seed["row"]["name"] if seed.get("row") else seed["name"]
                try:
                    sample = build_sample(engine, data_dir, name, seed["tag"],
                                          seed.get("row"), args.thresh, embed)
                    samples.append(sample)
                    print("[sample] %s（%s）变化占比 %.2f%%" % (name, seed["tag"], sample["ratio"] * 100.0))
                except Exception as exc:
                    print("[warn] 样本渲染失败 %s: %s" % (name, exc))
    else:
        print("[warn] 数据目录不可用或无 A/ 子目录: %s" % data_dir)

    # 3) 可选：大模型语义解释
    extra_note = ""
    if args.ai and samples:
        try:
            import explain as explain_mod
            import cv2
            best = samples[0]
            a_path = os.path.join(data_dir, "A", best["name"])
            b_path = os.path.join(data_dir, "B", best["name"])
            ok, text = explain_mod.explain(
                cv2.imread(a_path), cv2.imread(b_path),
                "变化像素占比: %.1f%%" % (best["ratio"] * 100.0))
            extra_note = ("AI 语义解释（%s）：%s" % (best["name"], text)) if ok else ("AI 语义解释调用失败：%s" % text)
            print("[ai]", ok)
        except Exception as exc:
            extra_note = "AI 语义解释调用失败：%s" % exc
            print("[warn] --ai 失败: %s" % exc)

    # 4) 生成报告
    bin_path = args.bin
    if not bin_path:
        for cand in (os.path.join(APP_DIR, "repbnet_cd.bin"),
                     os.path.abspath(os.path.join(APP_DIR, "..", "deploy", "repbnet_cd.bin"))):
            if os.path.exists(cand):
                bin_path = cand
                break

    html = build_html(dataset, metrics, samples, device_table(bin_path, engine),
                      build_analysis(metrics, samples, args.thresh),
                      build_conclusion(metrics, samples), extra_note)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    size_kb = os.path.getsize(args.out) / 1024.0
    print("\n[done] 报告已生成: %s（%.1f KB，样本 %d 组，指标 %d 条）"
          % (args.out, size_kb, len(samples), len(metrics)))


if __name__ == "__main__":
    main()