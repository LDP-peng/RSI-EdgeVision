#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webapp.py - RDK X5 遥感变化检测 Web 界面 (Flask)
参考：边缘遥感变化检测工作站（深蓝风格）

用法：
    板子: /usr/bin/python3 webapp.py
    浏览器自动打开 http://<板子IP>:5000
依赖：flask、numpy、opencv-python、Pillow、requests
"""
import os, sys, json, base64, socket, subprocess, threading, time, webbrowser
import numpy as np

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

import cv2
from flask import Flask, request, jsonify, render_template, abort, Response

from infer import InferEngine, compute_stats, stats_to_text
import explain as explain_mod

app = Flask(__name__)

# ---------- 全局模型（只加载一次） ----------
_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        binp = None
        for p in [os.path.join(APP_DIR, "repbnet_cd.bin"),
                  os.path.join(APP_DIR, "..", "deploy", "repbnet_cd.bin")]:
            p = os.path.abspath(p)
            if os.path.exists(p):
                binp = p
                break
        _ENGINE = InferEngine(binp)
    return _ENGINE


def im_data_url(bgr, ext=".jpg", quality=85):
    if bgr is None:
        return ""
    params = []
    if ext == ".jpg":
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    ok, buf = cv2.imencode(ext, bgr, params)
    if not ok:
        return ""
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return "data:%s;base64,%s" % (mime, base64.b64encode(buf).decode("utf-8"))


def run_infer(eng, a, b, thresh=0.5):
    a_bgr, b_bgr, x1, x2 = eng.preprocess(a, b)
    if eng.mock:
        prob = eng._mock_predict(a_bgr, b_bgr)
    else:
        prob = eng._real_predict(x1, x2)
    mask = (prob > thresh).astype(np.uint8) * 255
    overlay = b_bgr.copy()
    overlay[mask > 0] = (0, 0, 255)
    stats = compute_stats(mask, eng.size)
    heat = cv2.applyColorMap((np.clip(prob, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    return {"a_bgr": a_bgr, "b_bgr": b_bgr, "prob": prob, "mask": mask,
            "overlay": overlay, "heat": heat, "stats": stats}


def make_error_map(pred, gt):
    h, w = gt.shape
    img = np.zeros((h, w, 3), np.uint8)
    # 暗调柔和配色 (BGR)
    img[:, :] = (42, 58, 40)      # TN 暗青灰绿
    img[gt & ~pred] = (40, 128, 175)  # FN 暗琥珀
    img[pred & ~gt] = (48, 44, 152)   # FP 暗红
    img[pred & gt] = (58, 120, 48)    # TP 暗绿
    return img


def _read_cpu_stats():
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()[1:]
        return [int(x) for x in parts]
    except Exception:
        return None

_prev_cpu = None


def _cpu_percent():
    global _prev_cpu
    cur = _read_cpu_stats()
    if cur is None:
        return 0.0
    if _prev_cpu is None:
        _prev_cpu = cur
        time.sleep(0.12)
        cur = _read_cpu_stats()
        if cur is None:
            return 0.0
    dtotal = sum(cur) - sum(_prev_cpu)
    didle = (cur[3] + cur[4]) - (_prev_cpu[3] + _prev_cpu[4])
    _prev_cpu = cur
    if dtotal <= 0:
        return 0.0
    return max(0.0, min(100.0, (1.0 - didle / dtotal) * 100.0))


def _mem_pct():
    try:
        d = {}
        with open("/proc/meminfo") as f:
            for line in f:
                p = line.split(":")
                if len(p) < 2:
                    continue
                v = p[1].split()
                if p[0] in ("MemTotal", "MemAvailable") and v:
                    d[p[0]] = int(v[0])
        total = d.get("MemTotal", 0)
        avail = d.get("MemAvailable", total)
        if total <= 0:
            return 0.0
        return (1.0 - avail / total) * 100.0
    except Exception:
        return 0.0

def get_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None


def get_ip():
    try:
        out = subprocess.check_output(["hostname", "-I"]).decode().strip()
        if out:
            return out.split()[0]
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    eng = get_engine()
    return jsonify({
        "ok": True,
        "mock": bool(getattr(eng, "mock", True)),
        "model": getattr(eng, "model_name", None) or "repbnet_cd.bin",
        "runtime": "未检测" if getattr(eng, "mock", True) else "hbm_runtime",
        "temp": get_temp(),
        "mem": round(_mem_pct(), 1),
        "cpu": round(_cpu_percent(), 1),
        "ip": get_ip(),
        "size": int(getattr(eng, "size", 256)),
    })


@app.route("/api/list")
def api_list():
    d = (request.args.get("dir") or "").strip()
    if not d or not os.path.isdir(d):
        return jsonify({"ok": False, "error": "目录不存在: " + d}), 400
    a_dir = os.path.join(d, "A")
    b_dir = os.path.join(d, "B")
    names = []
    if os.path.isdir(a_dir) and os.path.isdir(b_dir):
        for n in sorted(os.listdir(a_dir)):
            ext = os.path.splitext(n)[1].lower()
            if ext not in (".png", ".jpg", ".jpeg", ".bmp"):
                continue
            if os.path.exists(os.path.join(b_dir, n)):
                names.append(n)
    return jsonify({"ok": True, "dir": d, "names": names})


@app.route("/api/img")
def api_img():
    d = (request.args.get("dir") or "").strip()
    n = (request.args.get("name") or "").strip()
    kind = (request.args.get("kind") or "A").strip().lower()
    if not d or not n:
        abort(400)
    if kind not in ("a", "b", "label"):
        abort(400)
    folder = {"a": "A", "b": "B", "label": "label"}[kind]
    p = os.path.join(d, folder, n)
    img = cv2.imread(p)
    if img is None:
        abort(404)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        abort(500)
    return Response(buf.tobytes(), mimetype="image/png")


@app.route("/api/detect", methods=["POST"])
def api_detect():
    try:
        d = request.get_json(force=True)
        a = (d.get("a") or "").strip()
        b = (d.get("b") or "").strip()
        if not a or not b:
            return jsonify({"ok": False, "error": "缺少 a/b 路径"}), 400
        thresh = float(d.get("thresh", 0.5))
        eng = get_engine()
        r = run_infer(eng, a, b, thresh)
        return jsonify({
            "ok": True, "mock": eng.mock,
            "size": int(eng.size),
            "stats": r["stats"],
            "stats_text": stats_to_text(r["stats"]),
            "a_img": im_data_url(r["a_bgr"]),
            "b_img": im_data_url(r["b_bgr"]),
            "overlay": im_data_url(r["overlay"]),
            "mask": im_data_url(r["mask"], ".png"),
            "prob": im_data_url(r["heat"]),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/eval", methods=["POST"])
def api_eval():
    try:
        d = request.get_json(force=True)
        a = (d.get("a") or "").strip()
        b = (d.get("b") or "").strip()
        label = (d.get("label") or "").strip()
        thresh = float(d.get("thresh", 0.5))
        if not a or not b or not label:
            return jsonify({"ok": False, "error": "缺少 a/b/label 路径"}), 400
        eng = get_engine()
        r = run_infer(eng, a, b, thresh)
        gt = cv2.imread(label, cv2.IMREAD_GRAYSCALE)
        if gt is None:
            return jsonify({"ok": False, "error": "label 读取失败: " + label}), 400
        pred = (r["mask"] > 0)
        if gt.shape[:2] != pred.shape:
            gt = cv2.resize(gt, (pred.shape[1], pred.shape[0]))
        gt = gt > 0
        tp = int((pred & gt).sum())
        fp = int((pred & ~gt).sum())
        fn = int((~pred & gt).sum())
        tn = int((~pred & ~gt).sum())
        prec = (tp / (tp + fp)) if (tp + fp) else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        iou = (tp / (tp + fp + fn)) if (tp + fp + fn) else 0.0
        err = make_error_map(pred, gt)
        return jsonify({
            "ok": True, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": prec, "recall": rec, "f1": f1, "iou": iou,
            "error_map": im_data_url(err, ".png"),
            "stats": r["stats"],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/explain", methods=["POST"])
def api_explain():
    try:
        d = request.get_json(force=True)
        a = (d.get("a") or "").strip()
        b = (d.get("b") or "").strip()
        if not a or not b:
            return jsonify({"ok": False, "error": "缺少 a/b 路径"}), 400
        eng = get_engine()
        r = run_infer(eng, a, b, 0.5)
        ok, txt = explain_mod.explain(r["a_bgr"], r["b_bgr"],
                                      stats_to_text(r["stats"]), r["overlay"])
        return jsonify({"ok": ok, "text": txt})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


def find_default_dir():
    cands = [
        os.path.join(APP_DIR, "demo"),
        os.path.join(APP_DIR, "test_256"),
        os.path.normpath(os.path.join(APP_DIR, "..", "test_256")),
        "/home/sunrise/deploy/test_256",
        "/home/ldp/LEVIR-CD-256/test",
        os.path.join(APP_DIR, "test"),
    ]
    for c in cands:
        if os.path.isdir(os.path.join(c, "A")) and os.path.isdir(os.path.join(c, "B")):
            return os.path.abspath(c)
    return None


@app.route("/api/default_dir")
def api_default_dir():
    d = find_default_dir()
    return jsonify({"ok": True, "dir": d or ""})

@app.route("/api/export", methods=["POST"])
def api_export():
    try:
        d = request.get_json(force=True)
        a = (d.get("a") or "").strip()
        b = (d.get("b") or "").strip()
        label = (d.get("label") or "").strip()
        thresh = float(d.get("thresh", 0.5))
        eng = get_engine()
        r = run_infer(eng, a, b, thresh)
        S = 256

        def rs(img):
            return cv2.resize(img, (S, S))

        tiles = [
            rs(r["a_bgr"]),
            rs(r["b_bgr"]),
            rs(r["overlay"]),
            rs(cv2.cvtColor(r["mask"], cv2.COLOR_GRAY2BGR)),
            rs(r["heat"]),
        ]
        if label and os.path.exists(label):
            gt = cv2.imread(label, cv2.IMREAD_GRAYSCALE)
            if gt is not None:
                pred = (r["mask"] > 0)
                if gt.shape[:2] != pred.shape:
                    gt = cv2.resize(gt, (pred.shape[1], pred.shape[0]))
                gt = gt > 0
                tiles.append(rs(make_error_map(pred, gt)))
        else:
            tiles.append(np.zeros((S, S, 3), np.uint8))
        grid = np.zeros((S * 3, S * 2, 3), np.uint8)
        for i, t in enumerate(tiles):
            rr, cc = i // 2, i % 2
            grid[rr * S:(rr + 1) * S, cc * S:(cc + 1) * S] = t
        return jsonify({"ok": True, "image": im_data_url(grid, ".png")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/report", methods=["POST"])
def api_report():
    """一键生成 HTML 格式评估报告（调用同目录 report.py）。"""
    try:
        d = request.get_json(silent=True) or {}
        data_dir = (d.get("dir") or "").strip() or find_default_dir() or os.path.join(APP_DIR, "demo")
        thresh = float(d.get("thresh", 0.5))
        n = int(d.get("samples", 3))
        out = os.path.join(APP_DIR, "report.html")
        cmd = [sys.executable, os.path.join(APP_DIR, "report.py"),
               "--data", data_dir, "--thresh", str(thresh),
               "--samples", str(n), "--out", out]
        if d.get("ai"):
            cmd.append("--ai")
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if not os.path.exists(out):
            return jsonify({"ok": False, "error": (p.stderr or p.stdout or "报告生成失败")[-500:]}), 400
        return jsonify({"ok": True, "url": "/report", "log": (p.stdout or "")[-800:]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/report")
def report_page():
    """查看已生成的评估报告。"""
    path = os.path.join(APP_DIR, "report.html")
    if not os.path.exists(path):
        return "尚未生成报告：请先在界面点击「导出评估报告」", 404
    with open(path, "r", encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


def open_browser_later():
    time.sleep(1.2)
    url = "http://127.0.0.1:5000"
    try:
        import shutil
        # 优先用 Firefox 全屏(KIOSK)模式：隐藏标签栏/地址栏，适合板载屏演示
        if shutil.which("firefox"):
            subprocess.Popen(["firefox", "--kiosk", url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[web] 已自动打开 Firefox(全屏):", url)
            return
        webbrowser.open(url)
        print("[web] 已自动打开浏览器(默认):", url)
    except Exception as e:
        print("[web] 自动打开失败:", e)


if __name__ == "__main__":
    ip = get_ip()
    print("Web UI: http://%s:5000" % ip)
    threading.Thread(target=open_browser_later, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, threaded=True)
