from PIL import Image, ImageDraw, ImageFont
import os

W,H=24,14
CE=16; GAP=2; PAD=8
X0=18; Y0=76
GRID_W=W*CE+(W-1)*GAP
GRID_H=H*CE+(H-1)*GAP
img=Image.new('RGB',(980,620),(11,18,32))
d=ImageDraw.Draw(img)

def font(sz, bold=False):
    for p in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\arial.ttf']:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except: pass
    return ImageFont.load_default()

def txt(x,y,s,sz=13,col=(219,230,255),bold=False):
    d.text((x,y),s,font=font(sz,bold),fill=col)

# rounded card
d.rounded_rectangle([8,8,972,612],radius=16,fill=(18,26,46),outline=(30,43,77),width=1)
# title
txt(30,26,'RSI-EdgeVision · 4D 时空数字孪生（示意）',20,(96,165,250))
# slider
d.rounded_rectangle([40,58,620,66],radius=4,fill=(30,43,77))
knob=440
d.ellipse([knob-8,50,knob+8,74],fill=(59,130,246))
txt(635,52,'2023',26,(59,130,246))

cols={'veg':(46,139,87),'water':(43,108,176),'bare':(160,131,90),'built':(125,138,155)}
# base
state=[]
for y in range(H):
    r=[]
    for x in range(W):
        t='veg'
        if 4<=y<=7 and 15<=x<=20: t='water'
        elif (8<=y<=12 and 16<=x<=23) or (5<=y<=7 and 12<=x<=14): t='bare'
        elif 9<=y<=11 and 3<=x<=6: t='built'
        r.append(t)
    state.append(r)

timeline=[
 (2,[(18,8,'built','new'),(19,8,'built','new'),(17,9,'built','new')]),
 (3,[(20,8,'built','new'),(18,9,'built','new'),(15,6,'bare','loss')]),
 (4,[(21,8,'built','new'),(19,9,'built','new'),(16,5,'bare','loss')]),
 (5,[(22,8,'built','new'),(20,9,'built','new'),(17,5,'bare','loss')]),
]
chg={}
for e,cells in timeline:
    for x,y,to,k in cells:
        chg[(x,y)]=k

for y in range(H):
    for x in range(W):
        c=state[y][x]
        if (x,y) in chg:
            c = '#ef4444' if chg[(x,y)]=='new' else '#f59e0b'
        else:
            c = cols[state[y][x]]
        px=X0+x*(CE+GAP); py=Y0+y*(CE+GAP)
        d.rounded_rectangle([px,py,px+CE,py+CE],radius=3,fill=c)

# legend
lx=40; ly=Y0+GRID_H+18
legend=[('植被',(46,139,87)),('水体',(43,108,176)),('裸地',(160,131,90)),('建成区',(125,138,155)),('变化(新增)',(239,68,68)),('变化(减少)',(245,158,11))]
for name,colr in legend:
    d.rounded_rectangle([lx,ly,lx+12,ly+12],radius=3,fill=colr)
    txt(lx+18,ly-1,name,13,(138,162,214))
    lx+=130

# right info panel
ix=700; iy=120
d.rounded_rectangle([ix-16,iy-20,956,300],radius=12,fill=(18,26,46),outline=(30,43,77))
txt(ix,iy-12,'点击图块查看详情',13,(138,162,214))
txt(ix,iy+14,'格点 (20,8) · 2023',15,(96,165,250))
txt(ix,iy+42,'🟥 新增变化：2020 从裸地',13,(219,230,255))
txt(ix,iy+64,'转为建成区，疑似新增建筑。',13,(219,230,255))
txt(ix,iy+94,'风险等级：中高',13,(245,158,11))

out=r'C:\Users\LDP\.codex\visualizations\2026\09\06\01a0758b-ebc1-77d1-a732-d983745cd83f\4dtwin.png'
img.save(out)
print('saved', out)
