#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infer.py — RDK X5 板端 REPBNet 变化检测推理封装。

提供 InferEngine：模型只加载一次，predict(a, b) 返回
    prob   : float32 [H,W] 概率图(0~1)
    mask   : uint8   [H,W] 二值掩码(0/255)
    overlay: BGR 图，变化区域标红
    stats  : 变化统计字典

若无 hbm_runtime（如电脑上测试），自动进入 mock 模式（用像素差异模拟），
界面会提示“模拟推理”，方便先看 GUI 布局。
预处理与训练完全一致（Transforms.py + train.py）。
"""
import os
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

MEAN = np.array([0.406, 0.456, 0.485, 0.406, 0.456, 0.485], dtype=np.float32)
STD = np.array([0.225, 0.224, 0.229, 0.225, 0.224, 0.229], dtype=np.float32)
SIZE = 256

try:
    import hbm_runtime
    _HAS_HBM = True
except ImportError:
    _HAS_HBM = False


class InferEngine:
    def __init__(self, bin_path=None, size=SIZE):
        if cv2 is None:
            raise RuntimeError("缺少 opencv，请先安装：pip install opencv-python")
        self.size = size
        self.mock = False
        self.model = None
        self.model_name = None
        self.input_names = None
        self.output_name = None
        if not _HAS_HBM:
            self.mock = True
            print("[infer] 未检测到 hbm_runtime，进入【模拟推理】模式(仅测试界面用)")
            return
        if not bin_path or not os.path.exists(bin_path):
            raise FileNotFoundError("找不到模型 .bin: %s" % bin_path)
        self.model = hbm_runtime.HB_HBMRuntime(bin_path)
        self.model_name = self.model.model_names[0]
        self.input_names = self.model.input_names[self.model_name]
        self.output_name = self.model.output_names[self.model_name][0]
        print("[infer] 模型:", self.model_name)
        print("[infer] 输入:", self.input_names, " 输出:", self.output_name)

    def preprocess(self, a_path, b_path):
        a = cv2.imread(a_path, cv2.IMREAD_COLOR)
        b = cv2.imread(b_path, cv2.IMREAD_COLOR)
        if a is None or b is None:
            raise FileNotFoundError("无法读取图片: %s / %s" % (a_path, b_path))
        if a.shape != b.shape:
            raise ValueError("A/B 尺寸不一致: %s vs %s" % (a.shape, b.shape))
        img6 = np.concatenate([a, b], axis=2).astype(np.float32)
        img6 /= 255.0
        img6 -= MEAN
        img6 /= STD
        if img6.shape[0] != self.size or img6.shape[1] != self.size:
            r = np.zeros((self.size, self.size, 6), np.float32)
            for c in range(6):
                r[:, :, c] = cv2.resize(img6[:, :, c], (self.size, self.size))
            img6 = r
        img6 = img6[:, :, ::-1].copy()
        img6 = img6.transpose(2, 0, 1)
        x1 = np.ascontiguousarray(img6[0:3])[None].astype(np.float32)
        x2 = np.ascontiguousarray(img6[3:6])[None].astype(np.float32)
        return a, b, x1, x2

    def _mock_predict(self, a, b):
        # 仅用于没有板子环境时预览 GUI；取像素平均绝对差作为“模拟概率”
        af = a.astype(np.float32)
        bf = b.astype(np.float32)
        diff = np.abs(af - bf).mean(axis=2)
        if diff.max() > 0:
            diff /= diff.max()
        prob = np.clip(diff, 0, 1).astype(np.float32)
        return prob

    def _real_predict(self, x1, x2):
        inputs = {self.model_name: {self.input_names[0]: x1, self.input_names[1]: x2}}
        outputs = self.model.run(inputs)
        out = np.asarray(outputs[self.model_name][self.output_name])
        return out.reshape(self.size, self.size).astype(np.float32)

    def predict(self, a_path, b_path):
        a, b, x1, x2 = self.preprocess(a_path, b_path)
        if self.mock:
            prob = self._mock_predict(a, b)
        else:
            prob = self._real_predict(x1, x2)
        mask = (prob > 0.5).astype(np.uint8) * 255
        overlay = b.copy()
        overlay[mask > 0] = (0, 0, 255)
        stats = compute_stats(mask, self.size)
        return {"prob": prob, "mask": mask, "overlay": overlay, "stats": stats, "mock": self.mock}


def compute_stats(mask, size):
    """返回变化统计：占比、面积、连通域数量、每个区域的近似位置。"""
    binar = (mask > 0).astype(np.uint8)
    ratio = float(binar.mean())
    area_px = int(binar.sum())
    num_labels, labels, stats_arr, centroids = cv2.connectedComponentsWithStats(binar, connectivity=8)
    regions = []
    for i in range(1, num_labels):
        x, y, w, h, area = stats_arr[i]
        if area <= 3:
            continue
        cx, cy = centroids[i]
        nx, ny = cx / size, cy / size
        pos = position_desc(nx, ny)
        regions.append({
            "x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "area": int(area), "cx": float(nx), "cy": float(ny),
            "pos": pos,
        })
    regions.sort(key=lambda r: -r["area"])
    return {
        "ratio": ratio, "area_px": area_px, "num": len(regions),
        "regions": regions[:20], "size": size,
    }


def position_desc(nx, ny):
    col = "左" if nx < 0.35 else ("中" if nx < 0.65 else "右")
    row = "上" if ny < 0.35 else ("中" if ny < 0.65 else "下")
    if row == "中":
        return col + "中部"
    return col + "侧" + row


def stats_to_text(stats):
    """把统计转成喂给大模型的文字。"""
    lines = []
    lines.append("变化像素占比: {:.1f}%".format(stats["ratio"] * 100))
    lines.append("变化区域数量: {} 处".format(stats["num"]))
    for i, r in enumerate(stats["regions"][:10]):
        pct = r["area"] / (stats["size"] * stats["size"]) * 100
        lines.append("  区域{}: 位于{}，面积约{:.1f}%，归一化位置({:.2f},{:.2f})".format(
            i + 1, r["pos"], pct, r["cx"], r["cy"]))
    return "\n".join(lines)


if __name__ == "__main__":
    # 简易命令行测试
    import sys
    if len(sys.argv) < 3:
        print("用法: python3 infer.py A.png B.png [bin]")
        sys.exit(1)
    binp = sys.argv[3] if len(sys.argv) > 3 else None
    eng = InferEngine(binp)
    r = eng.predict(sys.argv[1], sys.argv[2])
    print("[prob] min/max: {:.4f}/{:.4f}".format(r["prob"].min(), r["prob"].max()))
    print("[mask] 变化像素占比: {:.4f}".format(r["stats"]["ratio"]))
    print(stats_to_text(r["stats"]))
