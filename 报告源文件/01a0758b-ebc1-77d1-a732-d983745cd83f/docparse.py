# -*- coding: utf-8 -*-
import struct, sys, io

PATH = r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/tpl.doc"
data = open(PATH, "rb").read()
assert data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "not OLE2"

ssz  = 1 << struct.unpack_from("<H", data, 30)[0]
mssz = 1 << struct.unpack_from("<H", data, 32)[0]
num_fat      = struct.unpack_from("<I", data, 44)[0]
dir_start    = struct.unpack_from("<I", data, 48)[0]
mini_cutoff  = struct.unpack_from("<I", data, 56)[0]
mini_fat_st  = struct.unpack_from("<I", data, 60)[0]
difat_start  = struct.unpack_from("<I", data, 68)[0]
num_difat    = struct.unpack_from("<I", data, 72)[0]
END = 0xFFFFFFFA
def soff(sid): return 512 + sid * ssz

difat = list(struct.unpack_from("<109I", data, 76))
sid = difat_start
for _ in range(num_difat):
    if sid >= END: break
    ent = struct.unpack_from("<%dI" % (ssz // 4), data, soff(sid))
    difat.extend(ent[:-1]); sid = ent[-1]
difat = [x for x in difat if x < END][:num_fat]

fat = []
for s in difat:
    fat.extend(struct.unpack_from("<%dI" % (ssz // 4), data, soff(s)))

def chain(start):
    out, s, guard = [], start, 0
    while s < END and guard < 200000:
        out.append(s); s = fat[s] if s < len(fat) else END; guard += 1
    return out

def read_fat_stream(start, size=None):
    buf = bytearray()
    for s in chain(start):
        buf += data[soff(s): soff(s) + ssz]
    return bytes(buf[:size]) if size is not None else bytes(buf)

dirbuf = read_fat_stream(dir_start)
entries = []
for i in range(0, len(dirbuf), 128):
    e = dirbuf[i:i+128]
    if len(e) < 128: break
    nlen = struct.unpack_from("<H", e, 64)[0]
    name = e[:max(0, nlen-2)].decode("utf-16-le", "replace")
    typ  = e[66]
    if typ in (1, 2, 5):
        entries.append({
            "name": name, "type": typ,
            "start": struct.unpack_from("<I", e, 116)[0],
            "size":  struct.unpack_from("<Q", e, 120)[0],
        })
root = [e for e in entries if e["type"] == 5][0]
mini_stream = read_fat_stream(root["start"])
minifat = []
for s in chain(mini_fat_st):
    minifat.extend(struct.unpack_from("<%dI" % (ssz // 4), data, soff(s)))
def read_mini(start, size):
    buf, s, guard = bytearray(), start, 0
    while s < END and guard < 400000:
        buf += mini_stream[s*mssz:(s+1)*mssz]
        s = minifat[s] if s < len(minifat) else END; guard += 1
    return bytes(buf[:size])
def get_stream(name):
    for e in entries:
        if e["name"] == name and e["type"] == 2:
            return read_fat_stream(e["start"], e["size"]) if e["size"] >= mini_cutoff else read_mini(e["start"], e["size"])
    return None

print("流:", [e["name"] for e in entries if e["type"] == 2])

wd = get_stream("WordDocument")
flags = struct.unpack_from("<H", wd, 0x0A)[0]
tbl_name = "1Table" if (flags & 0x0200) else "0Table"
tbl = get_stream(tbl_name)
print("table stream:", tbl_name, len(tbl) if tbl else None)

fcClx, lcbClx = struct.unpack_from("<II", wd, 0x01A2)
clx = tbl[fcClx: fcClx + lcbClx]
# 跳过 Prc
i = 0
while i < len(clx) and clx[i] == 1:
    cb = struct.unpack_from("<h", clx, i+1)[0]
    i += 3 + cb
assert clx[i] == 2, "no Pcdt at %d" % i
lcb = struct.unpack_from("<I", clx, i+1)[0]
plc = clx[i+5: i+5+lcb]
n = (len(plc) - 4) // 12
cps = list(struct.unpack_from("<%dI" % (n+1), plc, 0))
pcds = plc[4*(n+1):]
out = []
for k in range(n):
    fc = struct.unpack_from("<I", pcds, k*8 + 2)[0]
    comp = bool(fc & 0x40000000)
    off = (fc & 0x3FFFFFFF) // 2 if comp else fc
    ln = cps[k+1] - cps[k]
    if comp:
        out.append(wd[off: off+ln].decode("cp1252", "replace"))
    else:
        out.append(wd[off: off+ln*2].decode("utf-16-le", "replace"))
text = "".join(out)
text = text.replace("\r", "\n").replace("\x07", "\t|")   # \x07 = 单元格/行结束
open(r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/tpl.txt", "w", encoding="utf-8").write(text)
print("=== 字数:", len(text))
print(text[:6000])
