#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 REPBNet 生成真实校准数据（多输入 float32 featuremap .bin）。

在虚拟机里运行（用 /usr/bin/python3），从已裁剪的 LEVIR-CD-256 训练集取样本，
做与训练完全一致的预处理，把 x1/x2 分别保存为 .bin，供 hb_mapper 校准使用。

用法：
    /usr/bin/python3 /mnt/hgfs/LEVIR-CD/quant/make_cal_data.py
"""

import os
import numpy as np
import cv2

# 虚拟机里已裁剪的 256 数据集
SRC = "/home/ldp/LEVIR-CD-256/train"          # 训练集 A/B
OUT = "/mnt/hgfs/LEVIR-CD/quant/cal_data"     # 写到共享目录，docker 挂载 /quant 后可见
N = 60                                        # 校准样本数（20~100 均可）

# 与 train.py / Transforms.py 完全一致（BGR 顺序）
MEAN = np.array([0.406, 0.456, 0.485, 0.406, 0.456, 0.485], dtype=np.float32)
STD = np.array([0.225, 0.224, 0.229, 0.225, 0.224, 0.229], dtype=np.float32)
SIZE = 256


def preprocess(a_path, b_path):
    a = cv2.imread(a_path)  # BGR
    b = cv2.imread(b_path)  # BGR
    if a is None or b is None:
        print("  读图失败，跳过:", a_path)
        return None, None
    img6 = np.concatenate([a, b], axis=2).astype(np.float32)  # H,W,6
    img6 /= 255.0
    img6 -= MEAN
    img6 /= STD
    if img6.shape[0] != SIZE or img6.shape[1] != SIZE:
        r = np.zeros((SIZE, SIZE, 6), np.float32)
        for c in range(6):
            r[:, :, c] = cv2.resize(img6[:, :, c], (SIZE, SIZE))
        img6 = r
    img6 = img6[:, :, ::-1].copy()       # 通道反转 BGR->RGB
    img6 = img6.transpose(2, 0, 1)       # [6,H,W]
    x1 = img6[0:3][None].astype(np.float32).copy()  # [1,3,H,W] 后时相 B RGB
    x2 = img6[3:6][None].astype(np.float32).copy()  # [1,3,H,W] 前时相 A RGB
    return x1, x2


def main():
    out_x1 = os.path.join(OUT, "x1")
    out_x2 = os.path.join(OUT, "x2")
    os.makedirs(out_x1, exist_ok=True)
    os.makedirs(out_x2, exist_ok=True)

    a_dir = os.path.join(SRC, "A")
    b_dir = os.path.join(SRC, "B")
    names = sorted(os.listdir(a_dir))[:N]
    ok = 0
    for i, nm in enumerate(names):
        x1, x2 = preprocess(os.path.join(a_dir, nm), os.path.join(b_dir, nm))
        if x1 is None:
            continue
        key = "{:04d}".format(i)
        x1.tofile(os.path.join(out_x1, key + ".bin"))
        x2.tofile(os.path.join(out_x2, key + ".bin"))
        ok += 1
    print("校准数据完成: {} 组，输出到 {}".format(ok, OUT))
    print("x1 单文件大小应为 {:.0f} 字节".format(1 * 3 * SIZE * SIZE * 4))


if __name__ == "__main__":
    main()
