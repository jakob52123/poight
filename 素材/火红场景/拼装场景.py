"""复用火红原版像素资产，重排为现有对战场；不复制原游戏地图或战斗代码。"""
from pathlib import Path
from PIL import Image, ImageDraw
from collections import Counter
import hashlib
import json
import math
import random
import re

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent.parent
ATLAS=Image.open(ROOT/'元瓦片.png').convert('RGBA')
TOP=Image.open(ROOT/'上层.png').convert('RGBA')
source=json.loads((ROOT/'原始/来源.json').read_text())
code=(PROJECT/'试玩模板.html').read_text()
raw=re.search(r'const obstacles=\[(.*?)\];',code,re.S).group(1)
obs=[]
for row in re.finditer(r"\{x:(\d+),y:(\d+),w:(\d+),h:(\d+),type:'(\w+)'\}",raw):
    x,y,w,h=map(int,row.groups()[:4]);obs.append(dict(x=x,y=y,w=w,h=h,type=row.group(5)))
assert len(obs)==10
rng=random.Random(20261010)
used=set()
def tile(i,upper=False):
    used.add(i)
    return (TOP if upper else ATLAS).crop((i%16*16,i//16*16,i%16*16+16,i//16*16+16))
def assemble(grid):
    im=Image.new('RGBA',(max(map(len,grid))*16,len(grid)*16))
    for y,row in enumerate(grid):
        for x,i in enumerate(row):im.alpha_composite(tile(i),(x*16,y*16))
    return im
# Original grass palette entries: the five turquoise ground colors, not tree greens.
GROUND_COLORS={(139,222,189),(164,230,197),(115,205,164),(65,180,139),(24,164,106)}
def clear_ground(im):
    out=im.copy();out.putdata([(r,g,b,0 if (r,g,b) in GROUND_COLORS else a) for r,g,b,a in im.get_flattened_data()]);return out
TREE=clear_ground(assemble([[0xE,0xF],[0x1E,0x1F],[0x26,0x27]]))
ROCK=clear_ground(tile(0x9F))
GROUND=Image.new('RGBA',(800,500),(115,205,164,255))
# Ground is rebuilt once offline. No per-frame procedural flicker or palette recolor.
for y in range(0,500,16):
    for x in range(0,800,16):
        i=rng.choice([1,1,1,1,8,9,0x10,0x11,0x13]);GROUND.alpha_composite(tile(i),(x,y))
# Dirt texture sampled from original tile; only replace ground-colored edge pixels.
dirt=tile(0xFF);counts=Counter(p for p in dirt.get_flattened_data() if p[:3] not in GROUND_COLORS and p[3]);base=counts.most_common(1)[0][0]
dirt.putdata([base if p[:3] in GROUND_COLORS else p for p in dirt.get_flattened_data()])
# Routes are walks, not collision geometry. Preserve the current arena's ten obstacles.
mask=Image.new('L',GROUND.size);md=ImageDraw.Draw(mask)
for rect in [(394,20,425,480),(26,287,770,319),(250,214,421,245),(250,214,281,305),(394,384,660,415)]:md.rectangle(rect,fill=255)
for xy in [(252,219),(392,287),(398,390),(654,386)]:md.ellipse((xy[0]-5,xy[1]-5,xy[0]+33,xy[1]+33),fill=255)
pattern=Image.new('RGBA',GROUND.size)
for y in range(0,500,16):
    for x in range(0,800,16):pattern.paste(dirt,(x,y))
# Grass-cut edge texture from original D1/E1/DA and its mirror; nearest pixels only.
path_tiles=Image.new('RGBA',GROUND.size)
for gy in range(32):
    for gx in range(50):
        x,y=gx*16,gy*16
        if mask.getpixel((min(x+8,799),min(y+8,499)))==0:continue
        path_tiles.alpha_composite(dirt,(x,y))
# The actual route mask is intentionally organic, not a hard rectangular tint.
edge_mask=mask.copy();pix=edge_mask.load();m=mask.load()
for y in range(1,499):
    for x in range(1,799):
        if not m[x,y]:continue
        if not all(m[x+dx,y+dy] for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]):pix[x,y]=160 if (x+y)%3 else 255
GROUND.paste(pattern,(0,0),edge_mask)
# Decorated verge: true FR grass and flower tiles, away from the initial fighters.
patches=[(80,206,7,2),(277,47,5,2),(480,50,7,3),(78,422,6,2),(631,301,7,3),(438,442,6,2)]
for x,y,cols,rows in patches:
    for yy in range(rows):
        for xx in range(cols):
            if (xx in (0,cols-1) and yy in (0,rows-1)) and rng.random()<.45:continue
            GROUND.alpha_composite(tile(0xD),(x+xx*16,y+yy*16))
for x,y in [(78,95),(165,42),(280,158),(52,248),(209,263),(375,164),(473,390),(591,427),(690,88),(735,214),(292,364),(354,317)]:
    GROUND.alpha_composite(clear_ground(tile(4)),(x,y))
# 不放无碰撞的岩石装饰：所有看似掩体的岩石必须对应真实碰撞体。
# Continuous perimeter uses original trees; remains outside playable center bounds.
for x in range(-16,816,24):
    GROUND.alpha_composite(TREE,(x,-17));GROUND.alpha_composite(TREE,(x,474))
for y in range(0,500,28):
    GROUND.alpha_composite(TREE,(-16,y));GROUND.alpha_composite(TREE,(786,y))

OBJECTS=Image.new('RGBA',(512,384));sprites=[];ox=oy=0;row_h=0

def repeat_to(src,size):
    dst=Image.new('RGBA',size)
    for y in range(0,size[1],src.height):
        for x in range(0,size[0],src.width):dst.alpha_composite(src,(x,y))
    return dst

def nine_slice(grid,w,h):
    # Native 16px corners; variable-size middle is tiled/cropped, never stretched.
    image=Image.new('RGBA',(w,h));left=min(16,w//2);right=min(16,w-left);up=min(16,h//2);down=min(16,h-up)
    widths=[left,w-left-right,right];heights=[up,h-up-down,down]
    py=0
    for yy,hh in enumerate(heights):
        px=0
        for xx,ww in enumerate(widths):
            if ww and hh:
                piece=tile(grid[yy][xx]);source_x=16-ww if xx==2 and ww<16 else 0;source_y=16-hh if yy==2 and hh<16 else 0
                if source_x or source_y:piece=piece.crop((source_x,source_y,16,16))
                image.alpha_composite(repeat_to(piece,(ww,hh)),(px,py))
            px+=ww
        py+=hh
    return clear_ground(image)

for number,o in enumerate(obs):
    w=math.ceil(o['w']/2);h=math.ceil(o['h']/2);overhang=0
    if o['type']=='trees':
        overhang=20;im=Image.new('RGBA',(w,h+overhang))
        # Canopies share a grounded dense patch; no invisible walkable gap in solid grove.
        floor=repeat_to(tile(0xD),(w,h));im.alpha_composite(floor,(0,overhang))
        cols=max(2,math.ceil(w/27));rows=max(2,math.ceil(h/26))
        for yy in range(rows):
            baseline=round((yy+1)*h/rows)+overhang
            for xx in range(cols):
                px=round(xx*(w-32)/(cols-1));im.alpha_composite(TREE,(px,baseline-48))
    elif o['type'] in ('log','hedge'):
        # Existing rectangular barrier becomes an actual FireRed hedge, not a fake wood block.
        basehedge=assemble([[0x13D,0x13E,0x13F],[0x14D,0x14E,0x14F]])
        im=Image.new('RGBA',(w,h));lh=min(16,h//2);rh=h-lh
        for yy,hh,sy in [(0,lh,0),(lh,rh,32-rh)]:
            for xx,ww,sx in [(0,16,0),(16,max(0,w-32),16),(w-16,16,32)]:
                if ww:im.alpha_composite(repeat_to(basehedge.crop((sx,sy,sx+16,sy+hh)),(ww,hh)),(xx,yy))
        im=clear_ground(im)
    else:
        # Original cliff/rock metatiles form a low boulder shelf with its visible footprint.
        im=nine_slice([[0x68,0x69,0x6A],[0x70,0x71,0x72],[0x78,0x79,0x7A]],w,h)
    if ox+im.width>512:ox=0;oy+=row_h+2;row_h=0
    assert oy+im.height<=384
    OBJECTS.alpha_composite(im,(ox,oy));sprites.append({'index':number,'sx':ox,'sy':oy,'w':im.width,'h':im.height,'x':o['x'],'y':o['y']-overhang*2,'z':o['y']+o['h'],'scale':2,'kind':o['type']});ox+=im.width+2;row_h=max(row_h,im.height)
# Crop unused atlas tail without changing sprite coordinates.
OBJECTS=OBJECTS.crop((0,0,512,oy+row_h))
GROUND.convert('RGB').save(ROOT/'草地底图.png',optimize=True)
OBJECTS.save(ROOT/'地形物件.png',optimize=True)
TREE.save(ROOT/'树木.png',optimize=True)
meta={'world':{'width':1600,'height':1000},'ground':'草地底图.png','groundNativeSize':[800,500],'objects':'地形物件.png','sprites':sprites,'collisionContract':obs,'sourceCommit':source['commit'],'usedMetatiles':[f'0x{i:03X}' for i in sorted(used)],'notes':['沿用原世界和十处碰撞范围；重新排列原版场景素材，不是原版地图复刻。','树冠允许向上伸出碰撞体，按脚底深度遮挡；草丛与花朵是可行走装饰。','原木障碍的美术换成原版绿篱，判定与位置保持不变。','未执行仓库C代码或下载ROM，不代表获得商业或公开传播授权。']}
for key in ['ground','objects']:
    f=ROOT/meta[key];meta[key+'SHA256']=hashlib.sha256(f.read_bytes()).hexdigest()
(ROOT/'场景包.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
preview=GROUND.convert('RGBA').resize((1600,1000),Image.Resampling.NEAREST)
for s in sorted(sprites,key=lambda x:x['z']):
    im=OBJECTS.crop((s['sx'],s['sy'],s['sx']+s['w'],s['sy']+s['h'])).resize((s['w']*2,s['h']*2),Image.Resampling.NEAREST)
    preview.alpha_composite(im,(s['x'],s['y']))
preview.save(ROOT/'场景预览.png',optimize=True)
print(json.dumps({'groundBytes':(ROOT/meta['ground']).stat().st_size,'objectsBytes':(ROOT/meta['objects']).stat().st_size,'sprites':len(sprites),'usedMetatiles':len(used),'noAIImageGeneration':True},ensure_ascii=False))
