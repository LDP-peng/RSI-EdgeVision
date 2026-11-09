p = r"E:\RSI‑EdgeVision：基于 RDK X5 的遥感地物智能解析系统\deploy\app.py"
s = open(p, encoding="utf-8").read()
old = "def main():\n    root = tk.Tk()\n    App(root)\n    root.mainloop()"
new = """def main():
    root = tk.Tk()
    if Image is None:
        messagebox.showwarning("缺少 Pillow", "未安装 Pillow，图片无法显示。\\n请安装：sudo apt install python3-pil python3-pil.imagetk 或 pip install Pillow")
    App(root)
    root.mainloop()"""
if old in s:
    s = s.replace(old, new)
    open(p, "w", encoding="utf-8").write(s)
    print("patched main")
else:
    print("pattern not found; current main:")
    import re
    m = re.search(r"def main\(\):.*?root\.mainloop\(\)", s, re.S)
    print(m.group(0) if m else "NOT FOUND")
