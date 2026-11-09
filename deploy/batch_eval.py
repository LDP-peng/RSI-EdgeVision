#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_eval.py — 在 RDK X5 板子上批量评估变化检测 test 集。

对 test 集的每一对 A/B：跑真实 .bin 模型 -> 得到概率图 -> 按阈值二值化
-> 与真实 label 逐像素比较 -> 累计 TP/FP/FN/TN -> 计算 精确率/召回率/F1/IoU。

用法（在板子 ~/deploy 下）：
    /usr/bin/python3 batch_eval.py --data test --bin repbnet_cd.bin --thresh 0.5 --limit 50
    # 不加 --limit 则跑整个 test 集

要求：data 目录下有 A/ B/ label/ 三个子文件夹，文件名一一对应。
"""
import os, sys, argparse, csv

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
import numpy as np
import cv2

from infer import InferEngine


def binarize(img, thresh=127):
    """把 label 归一成 0/1 数组。"""
    return (img > thresh).astype(np.uint8)


def safe_ratio(num, den):
    return float(num) / float(den) if den else 0.0


def eval_set(engine, data_dir, thresh=0.5, limit=None):
    a_dir = os.path.join(data_dir, "A")
    b_dir = os.path.join(data_dir, "B")
    l_dir = os.path.join(data_dir, "label")
    for d in (a_dir, b_dir, l_dir):
        if not os.path.isdir(d):
            raise FileNotFoundError("缺少目录: " + d)

    names = sorted(os.listdir(a_dir))
    if limit:
        names = names[:limit]

    # 累计混淆矩阵
    tp = fp = fn = tn = 0
    rows = []
    n = len(names)
    for idx, name in enumerate(names, 1):
        base, ext = os.path.splitext(name)
        a = os.path.join(a_dir, name)
        b = os.path.join(b_dir, name)
        l = os.path.join(l_dir, name)
        if not (os.path.exists(b) and os.path.exists(l)):
            print("[skip 缺失B或label]", name)
            continue
        res = engine.predict(a, b)
        prob = res["prob"]
        pred = (prob > thresh).astype(np.uint8)
        gt = binarize(cv2.imread(l, cv2.IMREAD_GRAYSCALE))
        if pred.shape != gt.shape:
            raise ValueError("尺寸不一致: %s pred=%s gt=%s" % (name, pred.shape, gt.shape))

        t = int(np.logical_and(pred == 1, gt == 1).sum())
        f = int(np.logical_and(pred == 1, gt == 0).sum())
        fnn = int(np.logical_and(pred == 0, gt == 1).sum())
        ttn = int(np.logical_and(pred == 0, gt == 0).sum())
        tp += t; fp += f; fn += fnn; tn += ttn

        prec = safe_ratio(t, t + f)
        rec = safe_ratio(t, t + fnn)
        f1 = safe_ratio(2 * prec * rec, prec + rec)
        iou = safe_ratio(t, t + f + fnn)
        rows.append([name, prec, rec, f1, iou, t, f, fnn, ttn])
        if idx % 50 == 0 or idx == n:
            print("进度 {}/{}".format(idx, n))

    prec = safe_ratio(tp, tp + fp)
    rec = safe_ratio(tp, tp + fn)
    f1 = safe_ratio(2 * prec * rec, prec + rec)
    iou = safe_ratio(tp, tp + fp + fn)
    return rows, {"precision": prec, "recall": rec, "f1": f1, "iou": iou,
                  "tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(APP_DIR, "test"))
    ap.add_argument("--bin", default=os.path.join(APP_DIR, "repbnet_cd.bin"))
    ap.add_argument("--thresh", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=os.path.join(APP_DIR, "eval_results.csv"))
    args = ap.parse_args()

    engine = InferEngine(args.bin)
    if engine.mock:
        print("[WARN] 当前为模拟推理（无 hbm_runtime），结果不代表真实模型！")

    rows, agg = eval_set(engine, args.data, args.thresh, args.limit)

    print("\n===== 总体指标（像素级，样本 %d 对）=====" % agg["n"])
    print("精确率 Precision : {:.4f}".format(agg["precision"]))
    print("召回率 Recall    : {:.4f}".format(agg["recall"]))
    print("F1              : {:.4f}".format(agg["f1"]))
    print("IoU             : {:.4f}".format(agg["iou"]))
    print("TP/FP/FN/TN     : {}/{}/{}/{}".format(agg["tp"], agg["fp"], agg["fn"], agg["tn"]))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "precision", "recall", "f1", "iou", "tp", "fp", "fn", "tn"])
        w.writerows(rows)
    print("\n已保存每张结果:", args.out)


if __name__ == "__main__":
    main()
