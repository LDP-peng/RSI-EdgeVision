#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDK X5 板端推理脚本：REPBNet 遥感变化检测。

用法（在板子上，模型和脚本同目录）：
    python3 rdx_infer.py --bin repbnet_cd.bin --pre A.png --post B.png --out change_mask.png

预处理与训练完全一致（Transforms.py + train.py）：
    cv2 读 A/B(BGR) -> 拼成 6 通道 -> /255 -> 均值/标准差归一化
    -> 通道反转[::-1] -> 转置 [6,H,W] -> x1=img[0:3]（后时相 B 的 RGB），x2=img[3:6]（前时相 A 的 RGB）

输出 change_map：[1,1,256,256] 概率图(0~1)，>0.5 判为变化。
"""

import argparse
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import hbm_runtime
except ImportError:
    hbm_runtime = None

# 与 train.py / Transforms.py 完全一致的归一化参数（BGR 顺序）
MEAN = np.array([0.406, 0.456, 0.485, 0.406, 0.456, 0.485], dtype=np.float32)
STD = np.array([0.225, 0.224, 0.229, 0.225, 0.224, 0.229], dtype=np.float32)
SIZE = 256


def load_image(path):
    if cv2 is None:
        raise RuntimeError("需要在板子上安装 opencv，例如：pip install opencv-python")
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError("无法读取图片: {}".format(path))
    return img  # BGR HxWx3


def preprocess(img1, img2, size=SIZE):
    """img1=pre/A, img2=post/B，均为 BGR。返回 (x1, x2)，float32 [1,3,size,size]。"""
    img6 = np.concatenate([img1, img2], axis=2).astype(np.float32)  # H,W,6
    img6 /= 255.0
    img6 -= MEAN
    img6 /= STD
    if img6.shape[0] != size or img6.shape[1] != size:
        # 逐通道缩放，规避 cv2 对任意通道 resize 的限制
        resized = np.zeros((size, size, 6), dtype=np.float32)
        for c in range(6):
            resized[:, :, c] = cv2.resize(img6[:, :, c], (size, size))
        img6 = resized
    img6 = img6[:, :, ::-1].copy()  # 通道反转
    img6 = img6.transpose(2, 0, 1)  # [6,H,W]
    x1 = np.ascontiguousarray(img6[0:3])  # 后时相 B 的 RGB
    x2 = np.ascontiguousarray(img6[3:6])  # 前时相 A 的 RGB
    return x1[None], x2[None]  # [1,3,H,W]


def run_model(bin_path, x1, x2):
    if hbm_runtime is None:
        raise RuntimeError("未找到 hbm_runtime，请确认在 RDK X5 板端运行（板端已自带）")
    model = hbm_runtime.HB_HBMRuntime(bin_path)
    model_name = model.model_names[0]
    input_names = model.input_names[model_name]
    output_names = model.output_names[model_name]
    print("[model] name   :", model_name)
    print("[model] inputs :", input_names)
    print("[model] outputs:", output_names)
    # 按 ONNX 顺序填入 x1 / x2
    inputs = {model_name: {input_names[0]: x1, input_names[1]: x2}}
    outputs = model.run(inputs)
    return np.asarray(outputs[model_name][output_names[0]])


def save_output(prob, out_path, threshold=0.5):
    prob = prob.reshape(SIZE, SIZE).astype(np.float32)
    mask = (prob > threshold).astype(np.uint8) * 255
    if cv2 is not None:
        cv2.imwrite(out_path, mask)
        cv2.imwrite(out_path + ".prob.png", (prob * 255).astype(np.uint8))
    else:
        np.save(out_path + ".mask.npy", mask)
        np.save(out_path + ".prob.npy", prob)
    print("[save] 掩码:", out_path)
    print("[info] 变化像素占比: {:.4f}".format(float((prob > threshold).mean())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True, help="量化后的 .bin 模型路径")
    ap.add_argument("--pre", required=True, help="前时相 A 图片")
    ap.add_argument("--post", required=True, help="后时相 B 图片")
    ap.add_argument("--out", default="change_mask.png", help="输出变化掩码 PNG")
    args = ap.parse_args()

    a = load_image(args.pre)
    b = load_image(args.post)
    if a.shape != b.shape:
        raise ValueError("A/B 尺寸不一致: {} vs {}".format(a.shape, b.shape))
    x1, x2 = preprocess(a, b)
    print("[pre] x1 shape:", x1.shape, "x2 shape:", x2.shape)
    print("[pre] x1 mean/std: {:.4f}/{:.4f}".format(float(x1.mean()), float(x1.std())))
    prob = run_model(args.bin, x1, x2)
    print("[out] raw shape:", prob.shape)
    save_output(prob, args.out)


if __name__ == "__main__":
    main()
