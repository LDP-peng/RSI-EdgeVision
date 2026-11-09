#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 best_model.pth 导出为 ONNX。

注意：本脚本的所在目录必须是 networks/ 的同级目录（脚本通过 __file__ 找到 networks/）。
预期目录结构：
    project/
      networks/
      best_model.pth
      export_onnx.py

用法（在虚拟机里，脚本所在目录下）：
    python3 export_onnx.py --weights best_model.pth --out best_model.onnx

模型：REPBNet baseline（use_rtrf=False, use_msrb=False），输入 x1/x2 各 [1,3,256,256]，
输出：最终变化图 change_map [1,1,256,256]（sigmoid 概率图，推理时 >0.5 即变化）。
"""

import argparse
import os
import sys

import torch
import torch.nn as nn


# 脚本所在目录，networks/ 是它的子目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from networks import REPBNet  # noqa: E402


def load_weights(model, path):
    ckpt = torch.load(path, map_location="cpu")
    if isinstance(ckpt, dict) and "state_dict" in ckpt:
        state = ckpt["state_dict"]
        print("[load] checkpoint 内含 state_dict")
    else:
        state = ckpt

    # 兼容 DataParallel 的 module. 前缀
    new_state = {}
    for k, v in state.items():
        if k.startswith("module."):
            new_state[k[len("module."):]] = v
        else:
            new_state[k] = v

    model.load_state_dict(new_state, strict=True)
    print(f"[load] 已加载权重: {path}")
    return model


class ExportModel(nn.Module):
    """只输出最终的变化图（原模型输出 tuple 的第 0 个）。"""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x1, x2):
        return self.model(x1, x2)[0]


def main():
    parser = argparse.ArgumentParser(description="导出 REPBNet 到 ONNX")
    parser.add_argument("--weights", default="best_model.pth", help="权重路径")
    parser.add_argument("--out", default="best_model.onnx", help="输出 ONNX 路径")
    args = parser.parse_args()

    model = REPBNet(
        pretrained_backbone=False,  # 不联网下载预训练权重，用 best_model.pth 里的
        use_rtrf=False,             # baseline 版本，与 best_model.pth 匹配
        use_msrb=False,             # baseline 版本
        use_scale_context_aggregation=True,
        use_cross_scale_detail_fusion=True,
    )
    model = load_weights(model, args.weights)
    model.eval()

    total_params = sum(p.numel() for p in model.parameters())
    print(f"[model] 总参数量: {total_params}")

    export_model = ExportModel(model)

    # 双时相输入，各 [1,3,256,256]
    x1 = torch.randn(1, 3, 256, 256)
    x2 = torch.randn(1, 3, 256, 256)

    with torch.no_grad():
        out = export_model(x1, x2)
        print(f"[check] 输出 shape: {tuple(out.shape)}")

        torch.onnx.export(
            export_model,
            (x1, x2),
            args.out,
            input_names=["x1", "x2"],
            output_names=["change_map"],
            opset_version=11,
            dynamo=False,
            do_constant_folding=True,
        )

    print(f"[done] 已保存: {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
