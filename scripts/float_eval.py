#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
float_eval.py - 浮点(PyTorch / CPU)全量评估 + CPU 单帧耗时对照。

一次跑出两样东西：
  1) 量化精度损失：用 best_model.pth（float32）在 test 集上全量推理，算
     P / R / F1 / IoU / Kappa / mIoU，与板端 int8 量化模型同口径对比。
  2) CPU 对照耗时：预热后统计 预处理 / 推理 / 后处理 / 端到端 的中位数，
     与 BPU 的 8.65 ms（纯推理）、40.91 ms（端到端）对比得出加速比。

预处理与 train.py / float_check.py / export_onnx.py / 量化校准数据完全一致：
  cv2 读 BGR -> 拼 6 通道 -> /255 -> 减均值 -> 除标准差 -> 通道反转(BGR->RGB) -> HWC->CHW
  x1 = 后时相 B 的 RGB，x2 = 前时相 A 的 RGB

用法：
  cd /mnt/hgfs/LEVIR-CD/project
  /usr/bin/python3 float_eval.py --limit 20      # 先小样本，验证跑得通
  /usr/bin/python3 float_eval.py                 # 全量 2048 对
  /usr/bin/python3 float_eval.py --threads 4     # 指定 CPU 线程数
"""
import os
import sys
import csv
import time
import argparse

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cv2
import torch

from networks import REPBNet

# 与 train.py 完全一致的归一化参数（BGR 顺序，重复两遍对应 A/B）
MEAN = np.array([0.406, 0.456, 0.485, 0.406, 0.456, 0.485], dtype=np.float32)
STD = np.array([0.225, 0.224, 0.229, 0.225, 0.224, 0.229], dtype=np.float32)
SIZE = 256

DEFAULT_DATA = "/home/ldp/LEVIR-CD-256/test"


def preprocess(a_path, b_path):
    """返回 x1(后时相 B 的 RGB)、x2(前时相 A 的 RGB)，形状均为 [1,3,256,256]。"""
    a = cv2.imread(a_path, cv2.IMREAD_COLOR)   # BGR
    b = cv2.imread(b_path, cv2.IMREAD_COLOR)   # BGR
    if a is None or b is None:
        raise FileNotFoundError("读图失败: %s / %s" % (a_path, b_path))
    img6 = np.concatenate([a, b], axis=2).astype(np.float32)   # H,W,6
    img6 /= 255.0
    img6 -= MEAN
    img6 /= STD
    if img6.shape[0] != SIZE or img6.shape[1] != SIZE:
        r = np.zeros((SIZE, SIZE, 6), np.float32)
        for c in range(6):
            r[:, :, c] = cv2.resize(img6[:, :, c], (SIZE, SIZE))
        img6 = r
    img6 = img6[:, :, ::-1].copy()          # ToTensor 通道反转 BGR->RGB
    img6 = img6.transpose(2, 0, 1)          # HWC -> CHW, [6,256,256]
    x = torch.from_numpy(img6.copy()).float().unsqueeze(0)
    x1 = x[:, 0:3].contiguous()             # 后时相 B RGB
    x2 = x[:, 3:6].contiguous()             # 前时相 A RGB
    return x1, x2


def load_weights(model, path):
    """兼容 module. 前缀与 {"state_dict": ...} 两种保存格式。"""
    ckpt = torch.load(path, map_location="cpu")
    state = ckpt["state_dict"] if (isinstance(ckpt, dict) and "state_dict" in ckpt) else ckpt
    new = {}
    for k, v in state.items():
        k2 = k[len("module."):] if k.startswith("module.") else k
        new[k2] = v
    model.load_state_dict(new, strict=True)
    return model


def safe_ratio(num, den):
    return float(num) / float(den) if den else 0.0


def kappa(tp, fp, fn, tn):
    n = tp + fp + fn + tn
    if n == 0:
        return 0.0
    po = float(tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / float(n * n)
    return (po - pe) / (1.0 - pe) if (1.0 - pe) != 0 else 0.0


def stat(arr):
    a = np.asarray(arr, dtype=np.float64)
    if a.size == 0:
        return dict(med=0.0, mean=0.0, p95=0.0, mn=0.0, mx=0.0)
    return dict(med=float(np.median(a)), mean=float(a.mean()),
                p95=float(np.percentile(a, 95)), mn=float(a.min()), mx=float(a.max()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA, help="test 集目录（内含 A/B/label）")
    ap.add_argument("--ckpt", default=os.path.join(HERE, "best_model.pth"))
    ap.add_argument("--thresh", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 对（快速验证用）")
    ap.add_argument("--warmup", type=int, default=10, help="计时前预热帧数")
    ap.add_argument("--threads", type=int, default=0, help=">0 则设置 torch CPU 线程数")
    ap.add_argument("--out", default=os.path.join(HERE, "float_eval_results.csv"))
    # 板端 int8 实测值，仅用于打印对照表
    ap.add_argument("--board-f1", type=float, default=0.8648)
    ap.add_argument("--board-iou", type=float, default=0.7617)
    ap.add_argument("--board-inf-ms", type=float, default=8.65)
    ap.add_argument("--board-e2e-ms", type=float, default=40.91)
    args = ap.parse_args()

    if args.threads > 0:
        torch.set_num_threads(args.threads)

    a_dir = os.path.join(args.data, "A")
    b_dir = os.path.join(args.data, "B")
    l_dir = os.path.join(args.data, "label")
    for d in (a_dir, b_dir, l_dir):
        if not os.path.isdir(d):
            raise FileNotFoundError("缺少目录: " + d)

    names = sorted(os.listdir(a_dir))
    names = [n for n in names if n.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"))]
    if args.limit:
        names = names[:args.limit]

    print("=" * 62)
    print("浮点(CPU)全量评估  REPB-Net / best_model.pth")
    print("数据目录 : %s" % args.data)
    print("样本数   : %d" % len(names))
    print("权重     : %s" % args.ckpt)
    print("torch    : %s   CPU 线程: %d" % (torch.__version__, torch.get_num_threads()))
    print("=" * 62)

    model = REPBNet(pretrained_backbone=False, use_rtrf=False, use_msrb=False,
                    use_scale_context_aggregation=True, use_cross_scale_detail_fusion=True)
    model = load_weights(model, args.ckpt)
    model.eval()

    tp = fp = fn = tn = 0
    rows = []
    t_pre_all, t_inf_all, t_post_all, t_tot_all = [], [], [], []
    n = len(names)
    t_start = time.time()

    with torch.no_grad():
        for idx, name in enumerate(names, 1):
            a_path = os.path.join(a_dir, name)
            b_path = os.path.join(b_dir, name)
            l_path = os.path.join(l_dir, name)
            if not (os.path.exists(b_path) and os.path.exists(l_path)):
                print("[skip 缺 B 或 label] %s" % name)
                continue

            t0 = time.perf_counter()
            x1, x2 = preprocess(a_path, b_path)
            t1 = time.perf_counter()
            out = model(x1, x2)[0]              # [1,1,256,256] 最细尺度输出
            t2 = time.perf_counter()
            prob = out.squeeze(0).squeeze(0).numpy().astype(np.float32)
            pred = (prob > args.thresh).astype(np.uint8)
            gt = (cv2.imread(l_path, cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8)
            if pred.shape != gt.shape:
                raise ValueError("尺寸不一致: %s pred=%s gt=%s" % (name, pred.shape, gt.shape))
            t3 = time.perf_counter()

            t = int(np.logical_and(pred == 1, gt == 1).sum())
            f = int(np.logical_and(pred == 1, gt == 0).sum())
            fnn = int(np.logical_and(pred == 0, gt == 1).sum())
            ttn = int(np.logical_and(pred == 0, gt == 0).sum())
            tp += t; fp += f; fn += fnn; tn += ttn

            prec = safe_ratio(t, t + f)
            rec = safe_ratio(t, t + fnn)
            f1 = safe_ratio(2 * prec * rec, prec + rec)
            iou = safe_ratio(t, t + f + fnn)
            rows.append([name, "%.6f" % prec, "%.6f" % rec, "%.6f" % f1, "%.6f" % iou,
                         t, f, fnn, ttn,
                         "%.3f" % ((t1 - t0) * 1000), "%.3f" % ((t2 - t1) * 1000),
                         "%.3f" % ((t3 - t2) * 1000), "%.3f" % ((t3 - t0) * 1000),
                         "%.4f" % float(pred.mean()), "%.4f" % float(gt.mean())])

            if idx > args.warmup:
                t_pre_all.append((t1 - t0) * 1000)
                t_inf_all.append((t2 - t1) * 1000)
                t_post_all.append((t3 - t2) * 1000)
                t_tot_all.append((t3 - t0) * 1000)

            if idx % 50 == 0 or idx == n:
                done = time.time() - t_start
                eta = done / idx * (n - idx)
                print("进度 %d/%d   已用 %.1f min   预计剩余 %.1f min"
                      % (idx, n, done / 60.0, eta / 60.0))

    prec = safe_ratio(tp, tp + fp)
    rec = safe_ratio(tp, tp + fn)
    f1 = safe_ratio(2 * prec * rec, prec + rec)
    iou = safe_ratio(tp, tp + fp + fn)
    iou_bg = safe_ratio(tn, tn + fp + fn)
    miou = (iou + iou_bg) / 2.0
    kap = kappa(tp, fp, fn, tn)

    n_sample = len(rows)
    print()
    print("=" * 62)
    print("浮点模型 总体指标（像素级累计，样本 %d 对）" % n_sample)
    print("=" * 62)
    print("精确率 Precision : %.4f" % prec)
    print("召回率 Recall    : %.4f" % rec)
    print("F1               : %.4f" % f1)
    print("IoU (变化类)     : %.4f" % iou)
    print("IoU (背景类)     : %.4f" % iou_bg)
    print("mIoU (两类平均)  : %.4f" % miou)
    print("Kappa            : %.4f" % kap)
    print("TP/FP/FN/TN      : %d/%d/%d/%d" % (tp, fp, fn, tn))

    sp, si, so, st = stat(t_pre_all), stat(t_inf_all), stat(t_post_all), stat(t_tot_all)
    print()
    print("-" * 62)
    print("CPU 单帧耗时（预热 %d 帧后，样本 %d 帧，单位 ms）" % (args.warmup, len(t_tot_all)))
    print("-" * 62)
    print("%-12s %10s %10s %10s %10s %10s" % ("阶段", "中位", "均值", "P95", "最小", "最大"))
    for label, s in (("预处理", sp), ("CPU 推理", si), ("后处理", so), ("端到端", st)):
        print("%-12s %10.2f %10.2f %10.2f %10.2f %10.2f"
              % (label, s["med"], s["mean"], s["p95"], s["mn"], s["mx"]))

    print()
    print("=" * 62)
    print("浮点(CPU) vs 量化(int8 / RDK X5 BPU) 对照")
    print("=" * 62)
    print("%-18s %16s %16s" % ("指标", "浮点 CPU", "量化 BPU"))
    print("%-18s %16s %16s" % ("单帧纯推理(ms)", "%.2f" % si["med"], "%.2f" % args.board_inf_ms))
    print("%-18s %16s %16s" % ("端到端(ms)", "%.2f" % st["med"], "%.2f" % args.board_e2e_ms))
    print("%-18s %16s %16s" % ("F1", "%.4f" % f1, "%.4f" % args.board_f1))
    print("%-18s %16s %16s" % ("IoU(变化类)", "%.4f" % iou, "%.4f" % args.board_iou))
    if si["med"] > 0:
        print("%-18s %16s" % ("推理加速比", "%.2fx" % (si["med"] / args.board_inf_ms)))
    if st["med"] > 0:
        print("%-18s %16s" % ("端到端加速比", "%.2fx" % (st["med"] / args.board_e2e_ms)))
    print("%-18s %16s" % ("F1 损失", "%+.4f" % (args.board_f1 - f1)))
    print("%-18s %16s" % ("IoU 损失", "%+.4f" % (args.board_iou - iou)))

    if rows:
        srt = sorted(rows, key=lambda r: float(r[3]))
        print()
        print("-" * 62)
        print("代表样本（可直接插报告）")
        print("-" * 62)
        for tag, r in (("最差", srt[0]), ("中位", srt[len(srt) // 2]), ("最优", srt[-1])):
            print("%s  %-22s F1=%-8s IoU=%-8s 预测变化占比=%s 真值=%s"
                  % (tag, r[0], r[3], r[4], r[12], r[13]))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "precision", "recall", "f1", "iou", "tp", "fp", "fn", "tn",
                    "pre_ms", "infer_ms", "post_ms", "total_ms",
                    "pred_change_ratio", "gt_change_ratio"])
        w.writerows(rows)
    print()
    print("每张结果已保存:", args.out)
    print("总耗时: %.1f min" % ((time.time() - t_start) / 60.0))


if __name__ == "__main__":
    main()
