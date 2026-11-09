p = r"E:\RSI‑EdgeVision：基于 RDK X5 的遥感地物智能解析系统\deploy\explain.py"
s = open(p, encoding="utf-8").read()
old = "import requests"
new = """try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    requests = None
    _HAS_REQUESTS = False"""
if old in s:
    s = s.replace(old, new, 1)
old2 = '    if cv2 is None:\n        return False, "缺少 opencv，无法处理图片"'
new2 = '    if not _HAS_REQUESTS:\n        return False, "缺少 requests，请安装：pip install requests"\n    if cv2 is None:\n        return False, "缺少 opencv，无法处理图片"'
if old2 in s:
    s = s.replace(old2, new2, 1)
open(p, "w", encoding="utf-8").write(s)
print("patched explain.py")
