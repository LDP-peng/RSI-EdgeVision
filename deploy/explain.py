#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
explain.py — 调用通义千问 qwen-vl-max，解释双时相图哪里变了。

流程：检测模型给出掩码/统计 -> 这里把 A、B 图(+叠加图)和统计文字发给视觉大模型
      -> 返回自然语言解释。

配置从 qwen_api.json 读取：api_key / base_url / model。
搜索顺序：本文件同目录 -> ./scripts -> ./deploy。
"""
import os, json, base64

try:
    import cv2
except ImportError:
    cv2 = None
try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    requests = None
    _HAS_REQUESTS = False

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONF = {
    "api_key": "",
    "base_url": "https://llm-mlsdsqfq32mzpqme.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-vl-max",
}


def find_config():
    for p in [os.path.join(HERE, "qwen_api.json"),
              os.path.join(HERE, "..", "scripts", "qwen_api.json"),
              os.path.join(HERE, "..", "deploy", "qwen_api.json")]:
        p = os.path.abspath(p)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return {**DEFAULT_CONF, **cfg}, p
    return dict(DEFAULT_CONF), None


def load_config():
    cfg, path = find_config()
    return cfg, path


def img_to_b64(img_bgr, size=512, quality=80):
    """把 BGR 图缩到 size 以内并转 JPEG base64。"""
    if img_bgr is None:
        return None
    h, w = img_bgr.shape[:2]
    scale = min(size / w, size / h)
    if scale < 1:
        img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return None
    return base64.b64encode(buf).decode("utf-8")


def explain(a_bgr, b_bgr, stats_text, overlay_bgr=None, cfg=None):
    """调用 qwen-vl-max。返回 (ok, text_or_error)。"""
    if cfg is None:
        cfg, _ = load_config()
    if not cfg.get("api_key"):
        return False, "未配置 API Key：请在 qwen_api.json 填写 api_key"
    if not _HAS_REQUESTS:
        return False, "缺少 requests，请安装：pip install requests"
    if cv2 is None:
        return False, "缺少 opencv，无法处理图片"

    b64_a = img_to_b64(a_bgr)
    b64_b = img_to_b64(b_bgr)
    content = [{"type": "text", "text": build_prompt(stats_text)}]
    if b64_a:
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64_a}})
    if b64_b:
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64_b}})
    if overlay_bgr is not None:
        b64_o = img_to_b64(overlay_bgr)
        if b64_o:
            content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64_o}})

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": "Bearer " + cfg["api_key"], "Content-Type": "application/json"}
    payload = {"model": cfg.get("model", "qwen-vl-max"),
               "messages": [{"role": "user", "content": content}], "max_tokens": 320, "temperature": 0.3}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=120)
    except requests.exceptions.Timeout:
        return False, "请求超时（网络或服务端较慢），请稍后再试"
    except Exception as e:
        return False, "网络错误: {}".format(e)
    if r.status_code != 200:
        return False, "API 返回 {}: {}".format(r.status_code, r.text[:300])
    data = r.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    return True, text


def build_prompt(stats_text):
    return ("你是遥感变化检测分析专家。请根据检测结果，用简洁中文说明双时相遥感影像中最主要的"
            "变化。\n\n要求：\n- 全文控制在100字以内\n- 只概括最重要的2~3处变化\n- 用短句分点，不要长篇大论\n- 直接说结论，不要解释模型或术语\n\n"
            "检测统计：\n" + stats_text + "\n\n"
            "请先一句话总览，再简短分点。")


if __name__ == "__main__":
    import sys
    from infer import InferEngine
    if len(sys.argv) < 3:
        print("用法: python3 explain.py A.png B.png [bin]")
        sys.exit(1)
    eng = InferEngine(sys.argv[3] if len(sys.argv) > 3 else None)
    a = cv2.imread(sys.argv[1])
    b = cv2.imread(sys.argv[2])
    res = eng.predict(sys.argv[1], sys.argv[2])
    text = stats_to_text(res["stats"])
    ok, out = explain(a, b, text, res.get("overlay"))
    print("[ok]", ok)
    print(out)
