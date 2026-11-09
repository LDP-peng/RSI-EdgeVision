
import numpy as np
from PIL import Image
src = open(r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/srcpath.txt", encoding="utf-8").read().strip()
a = np.array(Image.open(src).convert("L"))
H, W = a.shape
rows, cols = H//256, W//256
best = []
for c in range(cols):
    gt  = a[2*256:3*256, c*256:(c+1)*256]
    pr  = a[3*256:4*256, c*256:(c+1)*256]
    gt_ratio = (gt > 127).mean()
    pr_ratio = (pr > 127).mean()
    best.append((c, round(gt_ratio,4), round(pr_ratio,4)))
for b in best:
    print("col %d  GT %.4f  Pred %.4f" % b)
