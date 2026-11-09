#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试通义千问 qwen-vl-max：传两张本地图片，返回中文描述。
用法:
    python3 test_qwen_vl.py A.jpg B.jpg
Key 从环境变量 QWEN_API_KEY 读取，或放在同目录 qwen_api.json 里:
    {"api_key": "sk-ws-...", "base_url": "https://llm-xxx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", "model": "qwen-vl-max"}
"""
import sys, os, base64, json
import cv2
import requests

HERE = os.path.dirname(os.path.abspath(__file__))

def load_config():
    key = os.environ.get("QWEN_API_KEY", "")
    base_url = "https://llm-mlsdsqfq32mzpqme.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    model = "qwen-vl-max"
    cfg_path = os.path.join(HERE, "qwen_api.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        key = cfg.get("api_key", key)
        base_url = cfg.get("base_url", base_url)
        model = cfg.get("model", model)
    if not key:
        raise SystemExit("未找到 API Key。请设置环境变量 QWEN_API_KEY 或创建 qwen_api.json")
    return key, base_url, model

def img_to_b64(path, size=512, quality=80):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError("无法读取图片: " + path)
    h, w = img.shape[:2]
    scale = min(size / w, size / h)
    if scale < 1:
        img = cv2.resize(img, (int(w*scale), int(h*scale)))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("图片编码失败")
    return base64.b64encode(buf).decode("utf-8")

def main():
    if len(sys.argv) < 3:
        print("用法: python3 test_qwen_vl.py A.jpg B.jpg")
        sys.exit(1)
    a_path, b_path = sys.argv[1], sys.argv[2]
    key, base_url, model = load_config()

    b64_a = img_to_b64(a_path)
    b64_b = img_to_b64(b_path)

    user_text = ("请对比这两张遥感影像，说明发生了哪些变化、变化位置和大致类型。"
                 "用简洁的中文总结，指出主要变化区域。")

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64_a}},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64_b}},
            ]
        }]
    }
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    url = base_url.rstrip("/") + "/chat/completions"

    print("[call]", model)
    print("[url ]", url)
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    print("[status]", r.status_code)
    if r.status_code != 200:
        print(r.text[:2000])
        return
    data = r.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    print("[reply]")
    print(text)

if __name__ == "__main__":
    main()
