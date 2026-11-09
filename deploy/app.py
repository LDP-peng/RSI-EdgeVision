#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — RDK X5 变化检测 GUI（Tkinter 轻量版）

四页：
  1 选图与检测    2 结果可视化    3 指标    4 AI解释

需要：
  - 板端：hbm_runtime、opencv、Pillow、requests
    pip install requests Pillow opencv-python
  - 运行：/usr/bin/python3 app.py

AI解释调用通义千问 qwen-vl-max（配置在 qwen_api.json）。
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

from infer import InferEngine, stats_to_text
import explain as explain_mod


def find_bin():
    for p in [os.path.join(APP_DIR, "repbnet_cd.bin"),
              os.path.join(APP_DIR, "..", "deploy", "repbnet_cd.bin")]:
        p = os.path.abspath(p)
        if os.path.exists(p):
            return p
    return None


class App:
    def __init__(self, root):
        self.root = root
        root.title("RDK X5 遥感变化检测系统")
        root.geometry("960x720")

        self.engine = None
        self.last_result = None
        self.photos = {}  # 防止被 GC

        self.a_var = tk.StringVar()
        self.b_var = tk.StringVar()
        self.status_var = tk.StringVar(value="就绪")
        self.explain_status = tk.StringVar(value="尚未调用 AI")
        self.explain_text = None
        self.engine_status = tk.StringVar(value="模型未加载")
        self.api_status = tk.StringVar(value="API 未检测")

        self._init_engine()
        self._init_ui()
        self._set_default_paths()
        self._check_api()

    # ---------- 初始化 ----------
    def _init_engine(self):
        if cv2 is None:
            messagebox.showerror("缺少依赖", "未找到 opencv，请先安装：\npip install opencv-python")
            return
        binp = find_bin()
        try:
            self.engine = InferEngine(binp)
            if self.engine.mock:
                self.engine_status.set("模拟推理（未检测到 hbm_runtime，仅测试界面）")
            else:
                self.engine_status.set("模型已加载: " + os.path.basename(binp or "repbnet_cd.bin"))
        except Exception as e:
            self.engine_status.set("模型加载失败: " + str(e))

    def _check_api(self):
        cfg, path = explain_mod.load_config()
        if cfg.get("api_key"):
            self.api_status.set("API Key 已配置（" + cfg.get("model", "qwen-vl-max") + "）")
        else:
            self.api_status.set("API Key 未配置，请在 qwen_api.json 填写 api_key")

    def _set_default_paths(self):
        p = os.path.join(APP_DIR, "test", "A_test3.png")
        q = os.path.join(APP_DIR, "test", "B_test3.png")
        self.a_var.set(p if os.path.exists(p) else "")
        self.b_var.set(q if os.path.exists(q) else "")

    # ---------- UI ----------
    def _init_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        self.tab_detect = ttk.Frame(nb)
        self.tab_vis = ttk.Frame(nb)
        self.tab_metric = ttk.Frame(nb)
        self.tab_explain = ttk.Frame(nb)
        nb.add(self.tab_detect, text=" 1 选图与检测 ")
        nb.add(self.tab_vis, text=" 2 结果可视化 ")
        nb.add(self.tab_metric, text=" 3 指标 ")
        nb.add(self.tab_explain, text=" 4 AI 解释 ")

        self._build_detect()
        self._build_vis()
        self._build_metric()
        self._build_explain()

        # 底部状态栏
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, text="模型状态: ").pack(side="left", padx=4)
        ttk.Label(bar, textvariable=self.engine_status).pack(side="left")
        ttk.Label(bar, text="    API: ").pack(side="left", padx=(16, 0))
        ttk.Label(bar, textvariable=self.api_status).pack(side="left")
        ttk.Label(bar, text="    状态: ").pack(side="left", padx=(16, 0))
        ttk.Label(bar, textvariable=self.status_var).pack(side="left")

    def _build_detect(self):
        f = self.tab_detect
        ttk.Label(f, text="选择双时相遥感影像（前时相 A / 后时相 B）").grid(row=0, column=0, columnspan=3, padx=8, pady=8, sticky="w")
        ttk.Button(f, text="选择 A (前时相)", command=self._pick_a).grid(row=1, column=0, padx=8, pady=4)
        ttk.Entry(f, textvariable=self.a_var, width=60).grid(row=1, column=1, padx=4, pady=4)
        ttk.Button(f, text="选择 B (后时相)", command=self._pick_b).grid(row=2, column=0, padx=8, pady=4)
        ttk.Entry(f, textvariable=self.b_var, width=60).grid(row=2, column=1, padx=4, pady=4)

        ttk.Button(f, text="开始检测", command=self.on_detect).grid(row=3, column=0, padx=8, pady=16)
        ttk.Label(f, textvariable=self.status_var).grid(row=3, column=1, sticky="w", padx=8)

    def _build_vis(self):
        f = self.tab_vis
        self.labels = {}
        # 2 行 x 3 列
        titles = [
            ("A (前时相)", "a"), ("B (后时相)", "b"), ("变化叠加图(标红)", "overlay"),
            ("二值变化图", "mask"), ("概率热力图", "prob"), ("", ""),
        ]
        self.img_label = {}
        for idx, (title, key) in enumerate(titles):
            r, c = divmod(idx, 3)
            frame = ttk.Frame(f)
            frame.grid(row=r * 2, column=c, padx=8, pady=4)
            ttk.Label(frame, text=title).pack()
            lab = ttk.Label(frame, text="(未检测)", anchor="center")
            lab.pack()
            self.img_label[key] = lab

    def _build_metric(self):
        f = self.tab_metric
        ttk.Label(f, text="变化检测指标").grid(row=0, column=0, padx=8, pady=8, sticky="w", columnspan=2)
        self.metric_vars = {}
        rows = [("变化像素占比", "ratio"), ("变化区域数量", "num"), ("变化面积(像素)", "area_px"),
                ("测试图像尺寸", "size")]
        for i, (name, key) in enumerate(rows, start=1):
            ttk.Label(f, text=name + ":").grid(row=i, column=0, padx=8, pady=3, sticky="e")
            v = tk.StringVar(value="--")
            self.metric_vars[key] = v
            ttk.Label(f, textvariable=v).grid(row=i, column=1, padx=8, pady=3, sticky="w")

        ttk.Label(f, text="主要变化区域：").grid(row=len(rows) + 1, column=0, columnspan=2, padx=8, pady=(10, 2), sticky="w")
        self.metric_text = tk.Text(f, width=60, height=12, state="disabled")
        self.metric_text.grid(row=len(rows) + 2, column=0, columnspan=2, padx=8, pady=4)

    def _build_explain(self):
        f = self.tab_explain
        ttk.Button(f, text="调用 AI 解释（qwen-vl-max）", command=self.on_explain).grid(row=0, column=0, padx=8, pady=8, sticky="w")
        ttk.Label(f, textvariable=self.explain_status).grid(row=0, column=1, padx=8, sticky="w")
        self.explain_text = tk.Text(f, wrap="word", state="disabled")
        self.explain_text.grid(row=1, column=0, columnspan=2, padx=8, pady=4, sticky="nsew")
        f.rowconfigure(1, weight=1)
        f.columnconfigure(0, weight=1)

    # ---------- 事件 ----------
    def _pick_a(self):
        p = filedialog.askopenfilename(filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp")])
        if p:
            self.a_var.set(p)

    def _pick_b(self):
        p = filedialog.askopenfilename(filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp")])
        if p:
            self.b_var.set(p)

    def on_detect(self):
        if self.engine is None:
            messagebox.showerror("错误", "推理引擎未初始化（缺少 opencv 或模型）")
            return
        a = self.a_var.get().strip()
        b = self.b_var.get().strip()
        if not a or not b:
            messagebox.showerror("错误", "请先选择 A 和 B 图片")
            return
        self.status_var.set("正在推理...")
        threading.Thread(target=self._detect_worker, args=(a, b), daemon=True).start()

    def _detect_worker(self, a, b):
        try:
            r = self.engine.predict(a, b)
            self.root.after(0, lambda: self._show_result(r))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set("推理失败: " + str(e)))

    def _show_result(self, r):
        self.last_result = r
        self.status_var.set("检测完成" + ("（模拟推理）" if r.get("mock") else ""))
        # 显示 A/B（用原图）——这里通过 stats 拿不到原图，改从 predict 返回，见下
        self._populate_vis(r)

    # ---------- 图像显示 ----------
    def _show_img(self, key, bgr):
        if key == "" or bgr is None:
            return
        if key == "a":
            img = bgr
        elif key == "b":
            img = bgr
        elif key == "overlay":
            img = bgr
        elif key == "mask":
            img = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
        elif key == "prob":
            img = bgr
        else:
            return
        photo = self._to_photo(img)
        if photo is not None:
            self.img_label[key].config(image=photo, text="")
            self.photos[key] = photo

    def _to_photo(self, bgr):
        try:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(rgb)
            disp_w, disp_h = 230, 230
            im = im.resize((disp_w, disp_h))
            return ImageTk.PhotoImage(im)
        except Exception as e:
            return None

    def _populate_vis(self, r):
        # 需要用原始 A/B 图，predict 里已返回，但当前结果只有 mask/overlay/prob。
        # 这里从 explain 读取原图：为简化，重读路径。
        a = self.a_var.get().strip()
        b = self.b_var.get().strip()
        img_a = cv2.imread(a) if a else None
        img_b = cv2.imread(b) if b else None

        heatmap = None
        if r["prob"] is not None:
            p8 = (np.clip(r["prob"], 0, 1) * 255).astype(np.uint8)
            heatmap = cv2.applyColorMap(p8, cv2.COLORMAP_JET)

        self._show_img("a", img_a)
        self._show_img("b", img_b)
        self._show_img("overlay", r.get("overlay"))
        self._show_img("mask", r.get("mask"))
        self._show_img("prob", heatmap)

        self._populate_metric(r["stats"])

    def _populate_metric(self, s):
        self.metric_vars["ratio"].set("{:.2f}%".format(s["ratio"] * 100))
        self.metric_vars["num"].set(str(s["num"]))
        self.metric_vars["area_px"].set(str(s["area_px"]))
        self.metric_vars["size"].set("{}x{}".format(s["size"], s["size"]))
        text = stats_to_text(s)
        self.metric_text.config(state="normal")
        self.metric_text.delete("1.0", "end")
        self.metric_text.insert("1.0", text)
        self.metric_text.config(state="disabled")

    # ---------- AI 解释 ----------
    def on_explain(self):
        if self.last_result is None:
            messagebox.showinfo("提示", "请先点击“开始检测”，再调用 AI 解释")
            return
        a = self.a_var.get().strip()
        b = self.b_var.get().strip()
        img_a = cv2.imread(a) if a else None
        img_b = cv2.imread(b) if b else None
        stats_text = stats_to_text(self.last_result["stats"])
        overlay = self.last_result.get("overlay")
        self.explain_status.set("正在调用 AI...")
        self._set_explain_text("调用中，请稍候...")
        threading.Thread(target=self._explain_worker,
                         args=(img_a, img_b, stats_text, overlay), daemon=True).start()

    def _explain_worker(self, img_a, img_b, stats_text, overlay):
        ok, out = explain_mod.explain(img_a, img_b, stats_text, overlay)
        self.root.after(0, lambda: self._show_explain(ok, out))

    def _show_explain(self, ok, out):
        self.explain_status.set("完成" if ok else "失败")
        self._set_explain_text(out)

    def _set_explain_text(self, text):
        if self.explain_text is None:
            return
        self.explain_text.config(state="normal")
        self.explain_text.delete("1.0", "end")
        self.explain_text.insert("1.0", text)
        self.explain_text.config(state="disabled")


def main():
    import traceback
    root = tk.Tk()
    if Image is None:
        messagebox.showwarning("缺少 Pillow", "未安装 Pillow，图片无法显示。\n请安装：sudo apt install python3-pil python3-pil.imagetk 或 pip install Pillow")
    try:
        App(root)
    except Exception:
        traceback.print_exc()
        messagebox.showerror("启动出错", "初始化界面出错，详见终端日志")
        return
    root.mainloop()


if __name__ == "__main__":
    main()
