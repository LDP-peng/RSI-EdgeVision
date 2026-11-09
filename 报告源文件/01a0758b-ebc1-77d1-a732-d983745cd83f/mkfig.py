
import numpy as np
from PIL import Image
src = open(r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/srcpath.txt", encoding="utf-8").read().strip()
im = Image.open(src).convert("RGB")

def quad(col, out, scale=2):
    tiles = [im.crop((col*256, r*256, col*256+256, r*256+256)) for r in range(4)]
    W = 256*4
    canvas = Image.new("RGB", (W, 256), (0,0,0))
    for i, t in enumerate(tiles):
        canvas.paste(t, (i*256, 0))
    canvas = canvas.resize((W*scale, 256*scale), Image.LANCZOS)
    canvas.save(out)
    print("saved", out, canvas.size)

quad(1, r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/fig_quad_good.png")
quad(4, r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/fig_quad_fp.png")
