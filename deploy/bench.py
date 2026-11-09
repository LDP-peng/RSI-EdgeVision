#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench.py - RDK X5 边缘部署性能边界测试。

一次运行产出三张可直接贴进报告的表格：
    表1 延迟分解：预处理 / BPU 推理 / 后处理 / 端到端（中位延迟与 FPS）
    表2 稳定性曲线：连续运行 N 秒内的 FPS、温度、CPU 占用（无散热下的降频证据）
    表3 量化权衡：不同量化配置的 体积 x 精度 x 速度

输出文件：
    bench_report.md      报告正文（表格 + 收口结论草稿）
    bench_latency.csv    逐帧延迟明细
    bench_stability.csv  稳定性采样明细

用法（板子 ~/deploy 下）：
    /usr/bin/python3 bench.py --data test_256 --duration 300
    /usr/bin/python3 bench.py --quick                    # 只跑表1，约 1 分钟
    /usr/bin/python3 bench.py --threads 1,2,4            # 附带 hrt_model_exec 线程扫描
    /usr/bin/python3 bench.py --quant-cfg quant_cfg.json # 附带量化权衡表

注意：首次推理含内存分配，必须预热；统计取中位数而非均值。
"""
import os
import sys
import csv
import glob
import json
import time
import shutil
import argparse
import subprocess
import statistics

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)


# ------------------------------------------------------------ 系统信息读取
def read_temp_c():
    """读取所有 thermal zone 的最高温度（摄氏度），失败返回 None。"""
    best = None
    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            with open(path) as f:
                v = float(f.read().strip())
        except Exception:
            continue
        if v > 1000:          # 毫摄氏度
            v = v / 1000.0
        if best is None or v > best:
            best = v
    return best


def read_cpu_times():
    """读取 /proc/stat 第一行，返回 (busy, total)。"""
    try:
        with open("/proc/stat") as f:
            parts = [int(x) for x in f.readline().split()[1:]]
    except Exception:
        return None
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
    total = sum(parts)
    return total - idle, total


def cpu_percent(t0, t1):
    if not t0 or not t1:
        return None
    busy = t1[0] - t0[0]
    total = t1[1] - t0[1]
    return 100.0 * busy / total if total > 0 else None


def vm_rss_mb():
    """当前进程常驻内存（MB）。"""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / 1024.0
    except Exception:
        pass
    return None


def find_hrt_exec():
    p = shutil.which("hrt_model_exec")
    if p:
        return p
    for c in ("/usr/bin/hrt_model_exec", "/opt/hobot/bin/hrt_model_exec",
              "/usr/local/bin/hrt_model_exec"):
        if os.path.exists(c):
            return c
    return None


def fmt(value, digits=2, suffix=""):
    if value is None:
        return "-"
    return ("%." + str(digits) + "f%s") % (value, suffix)


def spark(values, width=48):
    """把一串数字画成字符曲线（不依赖字体，报告里不会乱码）。"""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    blocks = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    if hi - lo < 1e-9:
        return blocks[4] * min(len(values), width)
    step = max(1, len(values) // width)
    picked = values[::step][:width]
    return "".join(blocks[min(len(blocks) - 1, int((v - lo) / (hi - lo) * (len(blocks) - 1)))]
                   for v in picked)


# ------------------------------------------------------------ 表1：延迟分解
def bench_latency(engine, data_dir, warmup, frames, thresh):
    """分阶段计时：预处理 / 推理 / 后处理 / 端到端。"""
    import cv2
    import numpy as np

    name = None
    for cand in sorted(os.listdir(os.path.join(data_dir, "A"))):
        if os.path.exists(os.path.join(data_dir, "B", cand)):
            name = cand
            break
    if not name:
        raise RuntimeError("数据目录里没有成对的 A/B 影像: " + data_dir)
    a_path = os.path.join(data_dir, "A", name)
    b_path = os.path.join(data_dir, "B", name)

    def one():
        t0 = time.perf_counter()
        a_bgr, b_bgr, x1, x2 = engine.preprocess(a_path, b_path)
        t1 = time.perf_counter()
        prob = engine._mock_predict(a_bgr, b_bgr) if engine.mock else engine._real_predict(x1, x2)
        t2 = time.perf_counter()
        mask = (prob > thresh).astype(np.uint8) * 255
        overlay = b_bgr.copy()
        overlay[mask > 0] = (0, 0, 255)
        heat = cv2.applyColorMap((np.clip(prob, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
        t3 = time.perf_counter()
        return (t1 - t0, t2 - t1, t3 - t2, t3 - t0, mask, overlay, heat)

    for _ in range(max(0, warmup)):
        one()

    mem_before = vm_rss_mb()
    cpu_before = read_cpu_times()
    temp_before = read_temp_c()
    rows = []
    for i in range(frames):
        pre, inf, post, total, mask, overlay, heat = one()
        rows.append((i, pre * 1000, inf * 1000, post * 1000, total * 1000))
    cpu_after = read_cpu_times()
    temp_after = read_temp_c()
    mem_after = vm_rss_mb()

    med = lambda k: statistics.median([r[k] for r in rows])
    result = {
        "sample": name,
        "warmup": warmup,
        "frames": frames,
        "pre_ms": med(1), "infer_ms": med(2), "post_ms": med(3), "total_ms": med(4),
        "mean_ms": statistics.mean([r[4] for r in rows]),
        "min_ms": min(r[4] for r in rows),
        "max_ms": max(r[4] for r in rows),
        "fps": 1000.0 / med(4) if med(4) > 0 else None,
        "cpu_pct": cpu_percent(cpu_before, cpu_after),
        "mem_mb": mem_after,
        "mem_delta_mb": (mem_after - mem_before) if (mem_after and mem_before) else None,
        "temp_before": temp_before,
        "temp_after": temp_after,
        "rows": rows,
    }
    return result


# ------------------------------------------------------------ 表2：稳定性曲线
def bench_stability(engine, data_dir, duration, interval, thresh):
    """连续推理 duration 秒，每 interval 秒记录窗口 FPS、温度、CPU。"""
    import cv2
    import numpy as np

    name = None
    for cand in sorted(os.listdir(os.path.join(data_dir, "A"))):
        if os.path.exists(os.path.join(data_dir, "B", cand)):
            name = cand
            break
    a_path = os.path.join(data_dir, "A", name)
    b_path = os.path.join(data_dir, "B", name)

    probe = engine.preprocess(a_path, b_path)
    a_bgr, b_bgr, x1, x2 = probe

    def one():
        a_bgr, b_bgr, x1, x2 = engine.preprocess(a_path, b_path)
        return engine._mock_predict(a_bgr, b_bgr) if engine.mock else engine._real_predict(x1, x2)

    for _ in range(5):
        one()

    records = []
    t_start = time.perf_counter()
    win_count = 0
    win_t0 = t_start
    cpu_prev = read_cpu_times()
    while True:
        one()
        win_count += 1
        now = time.perf_counter()
        if now - win_t0 >= interval:
            cpu_now = read_cpu_times()
            fps = win_count / (now - win_t0)
            records.append({
                "t": now - t_start,
                "fps": fps,
                "temp": read_temp_c(),
                "cpu": cpu_percent(cpu_prev, cpu_now),
            })
            cpu_prev = cpu_now
            win_count = 0
            win_t0 = now
            print("  [%6.1fs] FPS %6.2f  温度 %s   CPU %s"
                  % (records[-1]["t"], fps, fmt(records[-1]["temp"], 1, "C"),
                     fmt(records[-1]["cpu"], 1, "%")))
            if now - t_start >= duration:
                break
        if time.perf_counter() - t_start > duration + interval * 3:
            break
    return name, records


# ------------------------------------------------------------ 表3：量化权衡
def bench_quant(engine_bin, rows, frames, thresh):
    """对每个候选量化模型测体积与速度，并从对应指标 CSV 读 F1/IoU。"""
    from infer import InferEngine

    data_dir = None
    for probe in (os.path.join(APP_DIR, "demo"), os.path.join(APP_DIR, "test_256")):
        if os.path.isdir(os.path.join(probe, "A")):
            data_dir = probe
            break

    out = []
    for row in rows:
        item = {"name": row.get("name") or os.path.basename(row.get("model", "")) or "-",
                "size_mb": None, "ms": None, "fps": None, "f1": None, "iou": None,
                "note": ""}
        model = row.get("model")
        if model and not os.path.isabs(model):
            model = os.path.join(APP_DIR, model)
        if model and os.path.exists(model):
            item["size_mb"] = os.path.getsize(model) / 1024.0 / 1024.0
            if data_dir:
                try:
                    eng = InferEngine(model)
                    if eng.mock:
                        item["note"] = "无 hbm_runtime，未测"
                    else:
                        import numpy as np
                        names = sorted(os.listdir(os.path.join(data_dir, "A")))
                        a_path = os.path.join(data_dir, "A", names[0])
                        b_path = os.path.join(data_dir, "B", names[0])
                        for _ in range(3):
                            eng.predict(a_path, b_path)
                        ts = []
                        for _ in range(max(5, frames)):
                            t0 = time.perf_counter()
                            eng.predict(a_path, b_path)
                            ts.append((time.perf_counter() - t0) * 1000)
                        item["ms"] = statistics.median(ts)
                        item["fps"] = 1000.0 / item["ms"] if item["ms"] else None
                except Exception as exc:
                    item["note"] = "测速失败: %s" % exc
        else:
            item["note"] = "模型文件不存在"

        mpath = row.get("metrics")
        if mpath:
            if not os.path.isabs(mpath):
                mpath = os.path.join(APP_DIR, mpath)
            if os.path.exists(mpath):
                try:
                    import report as report_mod
                    _, agg = report_mod.read_eval_csv(mpath)
                    item["f1"] = agg["f1"]
                    item["iou"] = agg["iou"]
                except Exception as exc:
                    item["note"] = (item["note"] + " 指标读取失败: %s") % exc
            else:
                item["note"] = (item["note"] + " 指标 CSV 不存在").strip()
        out.append(item)
    return out


# ------------------------------------------------------------ hrt_model_exec
def hrt_sweep(bin_path, threads, frames):
    """调用官方 hrt_model_exec perf 做线程数扫描（有则跑，无则跳过）。"""
    exe = find_hrt_exec()
    if not exe:
        return None, "未找到 hrt_model_exec，跳过线程扫描（板子自带，可 which hrt_model_exec 确认）"
    results = []
    for n in threads:
        cmd = [exe, "perf", "--model_file", bin_path,
               "--thread_num", str(n), "--frame_count", str(frames)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            out = (p.stdout or "") + (p.stderr or "")
        except Exception as exc:
            out = "执行失败: %s" % exc
        results.append({"threads": n, "output": out.strip()})
    return results, None


# ------------------------------------------------------------ 报告文本
def build_md(info, latency, stability, quant_rows, hrt, hrt_note):
    L = []
    L.append("# RDK X5 边缘部署性能边界测试")
    L.append("")
    L.append("生成时间：%s ｜ 模型：%s（%s）｜ 平台：%s"
             % (time.strftime("%Y-%m-%d %H:%M"), info["model_name"], info["model_size"], info["platform"]))
    L.append("")

    if info.get("mock"):
        L.append("> **注意：本次为模拟推理（未检测到 hbm_runtime），以下性能数据不代表真实模型，仅供流程联调。**")
        L.append("")

    L.append("## 表1 延迟分解（预热 %d 帧，统计 %d 帧，取中位数）"
             % (latency["warmup"], latency["frames"]))
    L.append("")
    L.append("| 阶段 | 中位耗时 (ms) | 说明 |")
    L.append("|---|---|---|")
    L.append("| 预处理 | %s | 读图、6 通道拼接、归一化 |" % fmt(latency["pre_ms"]))
    L.append("| BPU 推理 | %s | int8 定点前向 |" % fmt(latency["infer_ms"]))
    L.append("| 后处理 | %s | 二值化、叠加图、热力图 |" % fmt(latency["post_ms"]))
    L.append("| **端到端** | **%s** | 单帧全流程 |" % fmt(latency["total_ms"]))
    L.append("")
    L.append("- 端到端均值 %s ms，最小 %s ms，最大 %s ms"
             % (fmt(latency["mean_ms"]), fmt(latency["min_ms"]), fmt(latency["max_ms"])))
    L.append("- 单帧吞吐：**%s FPS**（按端到端中位延迟折算）" % fmt(latency["fps"]))
    L.append("- 进程 CPU 占用 %s，常驻内存 %s MB%s"
             % (fmt(latency["cpu_pct"], 1, "%"), fmt(latency["mem_mb"], 1),
                ("，推理前后增量 %s MB" % fmt(latency["mem_delta_mb"], 1)) if latency.get("mem_delta_mb") is not None else ""))
    L.append("- 温度：测试前 %s，测试后 %s"
             % (fmt(latency["temp_before"], 1, "C"), fmt(latency["temp_after"], 1, "C")))
    L.append("")

    if stability:
        L.append("## 表2 稳定性曲线（连续运行 %s 秒，每 %s 秒采样）"
                 % (fmt(stability[-1]["t"], 0), fmt(stability[1]["t"] - stability[0]["t"], 0) if len(stability) > 1 else "-"))
        L.append("")
        step = 1
        while (len(stability) + step - 1) // step > 13:
            step += 1
        shown = stability[::step]
        if shown[-1] is not stability[-1]:
            shown.append(stability[-1])
        if step > 1:
            L.append("（下表每 %d 个采样点取 1 个，完整曲线见 bench_stability.csv）" % step)
            L.append("")
        L.append("| 累计时间 (s) | 窗口 FPS | 温度 (C) | CPU (%) |")
        L.append("|---|---|---|---|")
        for r in shown:
            L.append("| %s | %s | %s | %s |"
                     % (fmt(r["t"], 0), fmt(r["fps"]), fmt(r["temp"], 1), fmt(r["cpu"], 1)))
        L.append("")
        fps_list = [r["fps"] for r in stability]
        temp_list = [r["temp"] for r in stability if r["temp"] is not None]
        L.append("FPS 曲线：`%s`" % spark(fps_list))
        if temp_list:
            L.append("")
            L.append("温度曲线：`%s`" % spark(temp_list))
        L.append("")
        first, last = fps_list[0], fps_list[-1]
        drop = (last - first) / first * 100.0 if first else 0.0
        L.append("- 首窗口 %s FPS → 末窗口 %s FPS（%+.1f%%）" % (fmt(first), fmt(last), drop))
        if temp_list:
            L.append("- 温度 %s C → %s C" % (fmt(temp_list[0], 1), fmt(temp_list[-1], 1)))
        L.append("")

    if quant_rows:
        L.append("## 表3 量化权衡（体积 x 精度 x 速度）")
        L.append("")
        L.append("| 配置 | 模型体积 (MB) | F1 | IoU | 端到端延迟 (ms) | FPS | 备注 |")
        L.append("|---|---|---|---|---|---|---|")
        for r in quant_rows:
            L.append("| %s | %s | %s | %s | %s | %s | %s |"
                     % (r["name"], fmt(r["size_mb"], 2), fmt(r["f1"], 4), fmt(r["iou"], 4),
                        fmt(r["ms"], 2), fmt(r["fps"], 2), r["note"] or "-"))
        L.append("")

    if hrt:
        L.append("## 附：hrt_model_exec 线程扫描")
        L.append("")
        for r in hrt:
            L.append("### thread_num = %d" % r["threads"])
            L.append("")
            L.append("```")
            L.append(r["output"][:1200])
            L.append("```")
            L.append("")
    elif hrt_note:
        L.append("## 附：hrt_model_exec 线程扫描")
        L.append("")
        L.append("未执行：%s" % hrt_note)
        L.append("")

    L.append("## 结论（可直接用于报告的收口句）")
    L.append("")
    parts = []
    parts.append("在 4 GB 内存的 RDK X5 上，模型端到端中位延迟 %s ms，单帧吞吐 %s FPS"
                 % (fmt(latency["total_ms"]), fmt(latency["fps"])))
    if stability:
        fps_list = [r["fps"] for r in stability]
        temp_list = [r["temp"] for r in stability if r["temp"] is not None]
        drop = (fps_list[-1] - fps_list[0]) / fps_list[0] * 100.0 if fps_list[0] else 0.0
        seg = "连续运行 %s 秒后 FPS 由 %s 变化到 %s（%+.1f%%）" % (fmt(stability[-1]["t"], 0), fmt(fps_list[0]), fmt(fps_list[-1]), drop)
        if temp_list:
            seg += "，温度由 %s C 升至 %s C" % (fmt(temp_list[0], 1), fmt(temp_list[-1], 1))
        parts.append(seg)
    L.append("，".join(parts) + "。")
    L.append("")
    if info.get("mock"):
        L.append("（本段数据来自模拟推理，需在板端重测后替换。）")
    return "\n".join(L)


# ------------------------------------------------------------ 落盘
def write_latency_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame", "preprocess_ms", "infer_ms", "postprocess_ms", "total_ms"])
        for r in rows:
            w.writerow(["%d" % r[0]] + ["%.4f" % v for v in r[1:]])


def write_stability_csv(path, records):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["elapsed_s", "fps", "temp_c", "cpu_pct"])
        for r in records:
            w.writerow(["%.1f" % r["t"], "%.3f" % r["fps"],
                        "" if r["temp"] is None else "%.2f" % r["temp"],
                        "" if r["cpu"] is None else "%.2f" % r["cpu"]])


def main():
    ap = argparse.ArgumentParser(description="RDK X5 边缘部署性能边界测试")
    ap.add_argument("--data", default=None, help="含 A/B 的数据目录（默认自动找 demo / test_256）")
    ap.add_argument("--model", default=None, help="量化模型 .bin（默认自动找 repbnet_cd.bin）")
    ap.add_argument("--thresh", type=float, default=0.5)
    ap.add_argument("--warmup", type=int, default=10, help="预热帧数，默认 10（必须预热）")
    ap.add_argument("--frames", type=int, default=100, help="表1 统计帧数，默认 100")
    ap.add_argument("--duration", type=float, default=300, help="表2 连续运行秒数，默认 300")
    ap.add_argument("--interval", type=float, default=10, help="表2 采样间隔秒数，默认 10")
    ap.add_argument("--quick", action="store_true", help="只跑表1，跳过稳定性测试")
    ap.add_argument("--threads", default=None, help="hrt_model_exec 线程扫描，如 1,2,4")
    ap.add_argument("--hrt-frames", type=int, default=200, help="线程扫描的帧数，默认 200")
    ap.add_argument("--quant-cfg", default=None,
                    help="量化权衡表配置 JSON：[{\"name\":..,\"model\":..,\"metrics\":..}]")
    ap.add_argument("--quant-frames", type=int, default=20, help="表3 每个模型的统计帧数")
    ap.add_argument("--out", default=os.path.join(APP_DIR, "bench_report.md"))
    args = ap.parse_args()

    # 模型与数据目录
    bin_path = args.model
    if not bin_path:
        for cand in (os.path.join(APP_DIR, "repbnet_cd.bin"),
                     os.path.abspath(os.path.join(APP_DIR, "..", "deploy", "repbnet_cd.bin"))):
            if os.path.exists(cand):
                bin_path = cand
                break
    if not bin_path or not os.path.exists(bin_path):
        print("[ERROR] 未找到量化模型 .bin，请用 --model 指定")
        return 1

    data_dir = args.data
    if not data_dir:
        for cand in (os.path.join(APP_DIR, "demo"), os.path.join(APP_DIR, "test_256")):
            if os.path.isdir(os.path.join(cand, "A")):
                data_dir = cand
                break
    if not data_dir or not os.path.isdir(os.path.join(data_dir, "A")):
        print("[ERROR] 未找到含 A/B 的数据目录，请用 --data 指定")
        return 1

    from infer import InferEngine
    engine = InferEngine(bin_path)
    if engine.mock:
        print("[WARN] 未检测到 hbm_runtime，进入模拟推理模式 —— 性能数据不代表真实模型！")
    print("[info] 模型 %s（%.2f MB）｜ 数据 %s" % (os.path.basename(bin_path),
                                                os.path.getsize(bin_path) / 1024.0 / 1024.0, data_dir))

    print("\n[表1] 延迟分解（预热 %d 帧，统计 %d 帧）..." % (args.warmup, args.frames))
    latency = bench_latency(engine, data_dir, args.warmup, args.frames, args.thresh)
    print("  预处理 %s ms ｜ 推理 %s ms ｜ 后处理 %s ms ｜ 端到端 %s ms（%s FPS）"
          % (fmt(latency["pre_ms"]), fmt(latency["infer_ms"]), fmt(latency["post_ms"]),
             fmt(latency["total_ms"]), fmt(latency["fps"])))
    write_latency_csv(os.path.join(APP_DIR, "bench_latency.csv"), latency["rows"])

    stability = []
    if args.quick:
        print("\n[表2] 已跳过（--quick）")
    else:
        print("\n[表2] 稳定性测试，连续运行 %s 秒（每 %s 秒采样）..."
              % (fmt(args.duration, 0), fmt(args.interval, 0)))
        try:
            _, stability = bench_stability(engine, data_dir, args.duration, args.interval, args.thresh)
            write_stability_csv(os.path.join(APP_DIR, "bench_stability.csv"), stability)
        except Exception as exc:
            print("  [warn] 稳定性测试失败: %s" % exc)

    quant_rows = []
    if args.quant_cfg:
        try:
            with open(args.quant_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            rows = cfg if isinstance(cfg, list) else cfg.get("rows", [])
            print("\n[表3] 量化权衡，共 %d 个配置..." % len(rows))
            quant_rows = bench_quant(bin_path, rows, args.quant_frames, args.thresh)
            for r in quant_rows:
                print("  %s：体积 %s MB ｜ F1 %s ｜ %s ms（%s FPS）%s"
                      % (r["name"], fmt(r["size_mb"], 2), fmt(r["f1"], 4),
                         fmt(r["ms"]), fmt(r["fps"]), (" ｜ " + r["note"]) if r["note"] else ""))
        except Exception as exc:
            print("  [warn] 量化权衡表失败: %s" % exc)

    hrt, hrt_note = (None, None)
    if args.threads:
        threads = [int(x) for x in str(args.threads).split(",") if x.strip()]
        print("\n[附] hrt_model_exec 线程扫描: %s" % threads)
        hrt, hrt_note = hrt_sweep(bin_path, threads, args.hrt_frames)
        if hrt_note:
            print("  " + hrt_note)
        else:
            for r in hrt:
                print("  thread_num=%d 完成" % r["threads"])

    info = {
        "model_name": os.path.basename(bin_path),
        "model_size": "%.2f MB" % (os.path.getsize(bin_path) / 1024.0 / 1024.0),
        "platform": "RDK X5（4 GB 内存 / BPU int8）",
        "mock": bool(engine.mock),
    }
    md = build_md(info, latency, stability, quant_rows, hrt, hrt_note)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    print("\n[done] 报告已生成: %s" % args.out)
    print("       明细: bench_latency.csv%s"
          % ("、bench_stability.csv" if stability else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())