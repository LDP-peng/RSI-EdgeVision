#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 LEVIR-CD 原始 1024x1024 影像裁成 256x256 的小图。

数据目录结构（原始）：
    <root>/train/A/xxx.png
    <root>/train/B/xxx.png
    <root>/train/label/xxx.png
    <root>/val/A/...
    <root>/val/B/...
    <root>/val/label/...
    <root>/test/A/...
    <root>/test/B/...
    <root>/test/label/...

输出目录结构（与输入一致）：
    <out>/train/A/xxx_c0_r0.png        # 第 0 列第 0 行，256x256
    <out>/train/A/xxx_c0_r1.png
    ...
    <out>/train/B/xxx_c0_r0.png        # 与 A 同名的裁剪，一一对应
    <out>/train/label/xxx_c0_r0.png
    ...

每张 1024x1024 会切成 4x4 = 16 张 256x256。A / B / label 的裁剪命名完全一致，
保证训练时能按文件名配对。

用法（在 Windows PowerShell 里运行）：
    python scripts\\LEVIR_caijian_256.py --root D:\\LEVIR-CD --out D:\\LEVIR-CD-256

如果老师已经给了他的裁剪脚本，请优先用老师那份；这份仅作兜底。
"""

import argparse
import os
from pathlib import Path

from PIL import Image


def crop_one(img_path: Path, out_path: Path, crop_size: int) -> int:
    """把单张图按 grid 裁成 crop_size 小图，返回小图数量。"""
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    count = 0
    for r in range(0, h, crop_size):
        for c in range(0, w, crop_size):
            box = (c, r, min(c + crop_size, w), min(r + crop_size, h))
            crop = img.crop(box)
            # 边缘若不足 crop_size，直接跳过，保证输出都是 256x256
            if crop.size != (crop_size, crop_size):
                continue
            name = out_path.stem + f"_c{c // crop_size}_r{r // crop_size}.png"
            crop.save(out_path.parent / name)
            count += 1
    return count


def process_split(split_dir: Path, out_split_dir: Path, crop_size: int) -> tuple:
    """处理一个 split(如 train)，返回 (配对组数, 裁剪总数)。"""
    pairs = 0
    crops = 0
    for sub in ("A", "B", "label"):
        src_dir = split_dir / sub
        dst_dir = out_split_dir / sub
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not src_dir.exists():
            continue
        for img_path in sorted(src_dir.iterdir()):
            if img_path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
                continue
            n = crop_one(img_path, dst_dir / img_path.stem, crop_size)
            crops += n
            if sub == "A":
                pairs += 1
    return pairs, crops


def main() -> None:
    parser = argparse.ArgumentParser(description="LEVIR-CD 裁剪 256x256")
    parser.add_argument("--root", required=True, help="原始数据集根目录")
    parser.add_argument("--out", required=True, help="输出根目录")
    parser.add_argument("--crop-size", type=int, default=256, help="裁剪尺寸，默认 256")
    args = parser.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    total_pairs = 0
    total_crops = 0
    for split in ("train", "val", "test"):
        src_split = root / split
        if not src_split.exists():
            continue
        pairs, crops = process_split(src_split, out / split, args.crop_size)
        total_pairs += pairs
        total_crops += crops
        print(f"[{split}] 配对图片 {pairs} 组，裁剪出 {crops} 张")

    print(f"\n完成。共 {total_pairs} 组图片，裁剪出 {total_crops} 张 256x256 小图。")
    print(f"输出目录：{out}")


if __name__ == "__main__":
    main()
