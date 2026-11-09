
from PIL import Image
src = open(r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/srcpath.txt", encoding="utf-8").read().strip()
im = Image.open(src)
W, H = im.size
cols, rows = W // 256, H // 256
print("size", im.size, "cols", cols, "rows", rows)
im.crop((0, 0, 256, 256 * rows)).save(r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/crop_probe.png")
print("ok")
