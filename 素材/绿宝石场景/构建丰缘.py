"""Build the original connected outdoor Hoenn component without altering source pixels."""
from pathlib import Path
from collections import deque
import base64, hashlib, json, math
from PIL import Image
from 解码地图 import ROOT,SRC,PIN,metatile,words,raw
from 打包草丛 import build_grass
from 构建通行 import extend_catalog
from 自由探索 import masks, legal
from 丰缘连接 import connected, seam_pairs, NAMES, OUTDOOR
OUT=ROOT/'丰缘全图';OUT.mkdir(exist_ok=True)
idx=json.loads((ROOT/'地图索引.json').read_text());assert idx['sourceCommit']==PIN
maps={m['id']:m for m in idx['maps'] if m['map_type'] in OUTDOOR};layouts={l['id']:l for l in idx['layouts']}
rows={k:json.loads((ROOT/'解码'/f"{layouts[m['layout']]['name']}.json").read_text()) for k,m in maps.items()}
maps,positions,seams,seam_report=connected(idx,rows)
PAD=8;SIZE=48;CHUNK=32
left=min(p[0] for p in positions.values())-PAD;top=min(p[1] for p in positions.values())-PAD
width=max(p[0]+rows[k]['width'] for k,p in positions.items())-left+PAD
height=max(p[1]+rows[k]['height'] for k,p in positions.items())-top+PAD
positions={k:(x-left,y-top) for k,(x,y) in positions.items()}
walk=bytearray(width*height);collision=bytearray([255])*(width*height);elevation=bytearray(width*height);behavior=bytearray(width*height);owner=[None]*(width*height)
# Preserve original metadata verbatim; the exploration table derives movement masks.
# Bridge metadata adds height-preserving layers, including the height3 wooden reflection deck.
WATER={0x10,0x11,0x12,0x13,0x14,0x15,0x18,0x19,0x1a,0x22,0x2a,0x2b}|set(range(0x50,0x54))
SPECIAL=set(range(0x30,0x40))|set(range(0x70,0x80))|set(range(0xd0,0xd7))
areas=[];blocked_special=0
for k,m in maps.items():
 row=rows[k];x,y=positions[k];w,h=row['width'],row['height']
 for j in range(h):
  for i in range(w):
   local=j*w+i;at=(y+j)*width+x+i;assert owner[at] is None,('overlap',k,owner[at]);owner[at]=k
   c,z,b=row['collision'][local],row['elevation'][local],row['behavior'][local];collision[at]=c;elevation[at]=z;behavior[at]=b;walk[at]=int(c==0 and ((b not in WATER and b not in SPECIAL) or (b==0x2b and z==3)))
   if c==0 and b in WATER|SPECIAL:blocked_special+=1
 areas.append({'id':k,'name':NAMES.get(m['name'],m['name'].replace('Route','')+'号道路'),'sourceName':m['name'],'x':x*SIZE,'y':y*SIZE,'w':w*SIZE,'h':h*SIZE,'gridX':x,'gridY':y,'columns':w,'rows':h,'sourceLayout':row['id']})
# 构建通行 resolves original warp fields only for the two contracted interiors.
chunks={}
def layer(cx,cy,key):
 c=chunks.setdefault((cx,cy),{});return c.setdefault(key,Image.new('RGBA',(CHUNK*16,CHUNK*16)))
def blit(im,px,py,key):
 x0,y0=px//(CHUNK*16),py//(CHUNK*16);x1,y1=(px+im.width-1)//(CHUNK*16),(py+im.height-1)//(CHUNK*16)
 for cy in range(y0,y1+1):
  for cx in range(x0,x1+1):
   if cx<0 or cy<0:continue
   dst=layer(cx,cy,key);dst.alpha_composite(im,(px-cx*CHUNK*16,py-cy*CHUNK*16))
# Border patterns from border.bin, not hand-drawn scenery. Collision stays closed outside maps.
for k,m in maps.items():
 row=rows[k];x,y=positions[k];w,h=row['width'],row['height'];layout=next(l for l in json.loads((SRC/'data/layouts/layouts.json').read_text())['layouts'] if l['id']==m['layout']);border=words(layout['border_filepath'])
 assert len(border)==4
 for j in range(-PAD,h+PAD):
  for i in range(-PAD,w+PAD):
   if 0<=i<w and 0<=j<h:continue
   lo,hi,_=metatile(row['primary'],row['secondary'],border[(j%2)*2+i%2]&1023);im=lo.copy();im.alpha_composite(hi);blit(im,(x+i)*16,(y+j)*16,'ground')
for k,m in maps.items():
 row=rows[k];x,y=positions[k]
 for key,source in [('ground','ground'),('over','over')]:
  p=ROOT/row['layers'][source]['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['layers'][source]['sha256'];im=Image.open(p).convert('RGBA');blit(im,x*16,y*16,key)

def emit(name,im):
 path=OUT/name;im.save(path,optimize=True);b=path.read_bytes();return {'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
preview=Image.new('RGBA',(width*2,height*2),(33,69,63,255));packed=[]
for (cx,cy),layers in sorted(chunks.items()):
 c={'x':cx*CHUNK*SIZE,'y':cy*CHUNK*SIZE,'w':CHUNK*SIZE,'h':CHUNK*SIZE}
 composite=Image.new('RGBA',(CHUNK*16,CHUNK*16))
 for key in ['ground','over']:
  im=layers.get(key)
  if im is not None and im.getbbox():c[key]=emit(f'{cx:02d}-{cy:02d}-{key}.png',im);composite.alpha_composite(im)
 preview.alpha_composite(composite.resize((CHUNK*2,CHUNK*2),Image.Resampling.NEAREST),(cx*CHUNK*2,cy*CHUNK*2));packed.append(c)
preview_ref=emit('全域缩略.png',preview)
blank=emit('空层.png',Image.new('RGBA',(1,1)))
# Apply the same explicit free-exploration policy to spawn selection and runtime masks.
walk,water=masks(collision,behavior)
components={};groups=[]
def neighbors(at):
 x,y=at%width,at//width
 for xx,yy in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
  if 0<=xx<width and 0<=yy<height:
   i=yy*width+xx
   if (walk[i] or water[i]) and legal(at,i,width,behavior,elevation,water):yield i
for at,v in enumerate(walk):
 if not (v or water[at]) or at in components:continue
 group=len(groups);q=deque([at]);components[at]=group;count=0
 while q:
  a=q.popleft();count+=1
  for n in neighbors(a):
   if n not in components:components[n]=group;q.append(n)
 groups.append(count)
seam_pairs(seams,positions,rows,width,walk,water,elevation,behavior)
seam_report['seams']=[e for e in seams if any(e['shift'])]
seam_report['worldOrigin']=[-left,-top]
(ROOT/'接缝表.json').write_text(json.dumps(seam_report,ensure_ascii=False,indent=2)+'\n')
scenes=[]
for name,zh in NAMES.items():
 if name=='SootopolisCity':continue
 area=next(a for a in areas if a['sourceName']==name);candidates=[]
 for j in range(area['rows']):
  for i in range(area['columns']):
   x,y=area['gridX']+i,area['gridY']+j;at=y*width+x
   spawn_mask=water if name=='PacifidlogTown' else walk
   if not spawn_mask[at] or groups[components[at]]<25:continue
   clearance=sum(spawn_mask[(y+dy)*width+x+dx] for dy in [-1,0,1] for dx in [-1,0,1]);distance=(i-area['columns']*.5)**2+(j-area['rows']*.6)**2
   candidates.append((clearance*20-distance,at))
 candidates.sort(reverse=True);pa=candidates[0][1];px,py=pa%width,pa//width
 enemy_options=[a for _,a in candidates if components[a]==components[pa] and 4<=math.hypot(a%width-px,a//width-py)<=7]
 assert enemy_options,name;ea=min(enemy_options,key=lambda a:abs(a//width-py)*3+abs(a%width-px-5))
 ex,ey=ea%width,ea//width
 localrow=rows[area['id']];g=Image.open(ROOT/localrow['layers']['ground']['path']).convert('RGBA');g.alpha_composite(Image.open(ROOT/localrow['layers']['over']['path']));g.thumbnail((400,250),Image.Resampling.NEAREST);pv=Image.new('RGBA',(400,250),(33,69,63,255));pv.alpha_composite(g,((400-g.width)//2,(250-g.height)//2));ref=emit(name+'-选址.png',pv)
 scenes.append({'id':'emerald-'+name.lower(),'name':zh,'description':'绿宝石原版布局 · 丰缘49张城镇、道路与海路连通世界。','terrainID':'hoenn-southwest','world':{'width':width*SIZE,'height':height*SIZE},'bounds':{'left':18,'right':width*SIZE-18,'top':18,'bottom':height*SIZE-18},'spawns':{'player':{'x':(px+.5)*SIZE,'y':(py+.5)*SIZE,'a':0},'enemy':{'x':(ex+.5)*SIZE,'y':(ey+.5)*SIZE,'a':math.pi}},'sprites':[],'collisionContract':[],'sourceCommit':PIN,'preview':ref['path'],'previewSHA256':ref['sha256'],'ground':preview_ref['path'],'groundSHA256':preview_ref['sha256'],'objects':blank['path'],'objectsSHA256':blank['sha256'],'areaID':area['id']})
terrain={'id':'hoenn-southwest','fieldEffects':build_grass(),'cellSize':SIZE,'columns':width,'rows':height,'walkB64':base64.b64encode(walk).decode(),'elevationB64':base64.b64encode(elevation).decode(),'collisionB64':base64.b64encode(collision).decode(),'behaviorB64':base64.b64encode(behavior).decode(),'areas':areas,'chunks':packed,'preview':preview_ref,'world':{'width':width*SIZE,'height':height*SIZE},'seams':seams}
terrain['streaming']=True
terrain['geometryVersion']=2
limitations=['49 connected outdoor maps; Sootopolis separate; Frontier/Safari excluded', 'No NPC/story/underwater maps; two original interiors only', 'Bridge layers preserved; policy table owns exploration traversal; static water art']
catalog=extend_catalog(ROOT,{'default':'emerald-littleroottown','scenes':scenes,'terrains':[terrain],'limitations':limitations},idx,WATER|SPECIAL)
(ROOT/'场景目录.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+'\n')
report={'sourceCommit':PIN,'decodedMapRecords':len(idx['maps']),'playableSourceMaps':sum(len(t['areas']) for t in catalog['terrains']),'outdoorSourceMaps':len(maps),'spawnPresets':sum(not s.get('entranceOnly',False) for s in scenes),'world':terrain['world'],'chunks':len(packed),'chunkNativeMaximum':[512,512],'walkableCells':sum(walk),'components':sorted(groups,reverse=True),'seams':seams,'conservativeSpecialBlocks':blocked_special,'paidAPICalls':0,'limitations':catalog['limitations']}
(OUT/'构建核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('seams','components')},ensure_ascii=False,indent=2))
