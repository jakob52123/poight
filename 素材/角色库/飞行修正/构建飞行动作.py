"""仅处理首发50中的8只飞行系。原生振翅/腾空姿态重新编排，固定躯干锚点去除地面跳跃轨迹。"""
from pathlib import Path
from urllib.request import Request,urlopen
from PIL import Image
import xml.etree.ElementTree as ET
import hashlib,json,math
ROOT=Path(__file__).resolve().parent;LIB=ROOT.parent
# 非新画专用动画：Hover直接选周期；无Hover者重组原生翼姿。暴鲤龙无翼，保留躯干蜿蜒。
CHOICES={6:('Hop',[0,5,0,5],[.16,.16,.16,.16]),21:('Hover',[0,1,2,3],[.10]*4),123:('Hop',[0,1,0,1],[.055]*4),130:('Walk',[0,1,2,3],[.18]*4),144:('Walk',[0,1,2,3],[.14]*4),145:('Walk',[0,1,2,3],[.12]*4),146:('Hover',[0,1,2,3],[.14]*4),149:('Hop',[6,8,9,8],[.14]*4)}
ORDER=[0,7,6,5,4,3,2,1];overrides={};receipts=[]
for n,(name,frames,durations) in CHOICES.items():
 raw=LIB/f'原始/{n:04}';a=next(a for a in ET.parse(raw/'AnimData.xml').getroot().findall('.//Anim') if a.findtext('Name')==name);fw,fh=int(a.findtext('FrameWidth')),int(a.findtext('FrameHeight'))
 for suffix in ['Anim','Offsets']:
  f=raw/f'{name}-{suffix}.png';url=f'https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/sprite/{n:04}/{name}-{suffix}.png'
  if not f.exists():
   with urlopen(Request(url,headers={'User-Agent':'pocket-flight-fix'}),timeout=15) as r:data=r.read(2000000)
   from io import BytesIO
   Image.open(BytesIO(data)).verify();f.write_bytes(data)
  receipts.append({'id':n,'url':url,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 im=Image.open(raw/f'{name}-Anim.png').convert('RGBA');off=Image.open(raw/f'{name}-Offsets.png').convert('RGBA');assert im.size==off.size and im.height==fh*8
 cells=[];bounds=[];unique=[]
 for row in ORDER:
  poses=set()
  for frame in frames:
   tile=im.crop((frame*fw,row*fh,(frame+1)*fw,(row+1)*fh));markers=off.crop((frame*fw,row*fh,(frame+1)*fw,(row+1)*fh))
   green=[(x,y) for y in range(fh) for x in range(fw) if markers.getpixel((x,y)) in [(0,255,0,255),(255,255,0,255),(0,255,255,255),(255,255,255,255)]]
   # SpriteCollab marker channels may overlap: green channel is the body marker.
   assert len(green)==1,(n,name,row,frame,'body marker',green)
   x,y=green[0];box=tile.getbbox();assert box
   bounds.append((box[0]-x,box[1]-y,box[2]-x,box[3]-y));cells.append((tile,x,y));poses.add(hashlib.sha256(tile.crop(box).tobytes()).hexdigest())
  unique.append(len(poses))
 assert min(unique)>=2,(n,unique)
 lx,ly=min(b[0] for b in bounds),min(b[1] for b in bounds);rx,ry=max(b[2] for b in bounds),max(b[3] for b in bounds)
 cw,ch=math.ceil((rx-lx+4)/2)*2,math.ceil((ry-ly+4)/2)*2;ax,ay=2-lx,2-ly;atlas=Image.new('RGBA',(cw*len(frames),ch*8))
 for i,(tile,x,y) in enumerate(cells):
  cell=Image.new('RGBA',(cw,ch));cell.paste(tile,(ax-x,ay-y));assert sum(v>0 for v in cell.getchannel('A').get_flattened_data())==sum(v>0 for v in tile.getchannel('A').get_flattened_data());atlas.paste(cell,(i%len(frames)*cw,i//len(frames)*ch))
 file=ROOT/f'{n:04}-Air.png';atlas.save(file,optimize=True);source=f'Air-{name}';art={'file':str(file.relative_to(LIB)),'frameWidth':cw,'frameHeight':ch,'frames':len(frames),'rows':8,'anchorX':ax,'anchorY':ay,'durations':durations,'totalDuration':sum(durations),'hitFrame':None,'hitTime':None,'sourceAnimation':source,'roleFallback':False}
 overrides[str(n)]={'art':art,'audit':{'rows':8,'frames':len(frames),'distinctPoses':unique,'pixelCountPreserved':True,'clippedFrames':0,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()},'sourceAnimation':name,'sourceFrames':frames,'flightHeight':48 if n!=130 else 56,'method':'原生姿态重新编排，逐帧以Offsets躯干锚点对齐；非原版完整专用飞行循环','roles':['idle','walk','dash']}
# 其余出招/受击仍保留原生动作，但绘制时以躯干定位，避免从飞行突然跳回脚底锚点。
for n in CHOICES:
 c=json.loads((LIB/f'{n:04}/角色.json').read_text());body_offsets={}
 for role in ['shoot','melee','hurt']:
  old=c['art'][role];name=old['sourceAnimation'];raw=LIB/f'原始/{n:04}';a=next(a for a in ET.parse(raw/'AnimData.xml').getroot().findall('.//Anim') if a.findtext('Name')==name);fw,fh=int(a.findtext('FrameWidth')),int(a.findtext('FrameHeight'));f=raw/f'{name}-Offsets.png';url=f'https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/sprite/{n:04}/{name}-Offsets.png'
  if not f.exists():
   with urlopen(Request(url,headers={'User-Agent':'pocket-flight-fix'}),timeout=15) as r:data=r.read(2000000)
   from io import BytesIO
   Image.open(BytesIO(data)).verify();f.write_bytes(data)
  receipts.append({'id':n,'url':url,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
  offsets=Image.open(f).convert('RGBA');shadow=Image.open(raw/f'{name}-Shadow.png').convert('RGBA');values=[]
  for row in ORDER if old['rows']==8 else [0]:
   s=shadow.crop((0,row*fh,fw,(row+1)*fh));roots=[(x,y) for y in range(fh) for x in range(fw) if s.getpixel((x,y))==(255,255,255,255)];assert len(roots)==1;rx,ry=roots[0];line=[]
   for frame in range(old['frames']):
    s=offsets.crop((frame*fw,row*fh,(frame+1)*fw,(row+1)*fh));markers=[(x,y) for y in range(fh) for x in range(fw) if s.getpixel((x,y)) in [(0,255,0,255),(255,255,0,255),(0,255,255,255),(255,255,255,255)]];assert len(markers)==1,(n,role,frame,markers);gx,gy=markers[0];line.append([gx-rx,gy-ry])
   values.append(line)
  body_offsets[role]=values
 overrides[str(n)]['bodyOffsets']=body_offsets
(ROOT/'飞行包.json').write_text(json.dumps(overrides,ensure_ascii=False,indent=2)+'\n');(ROOT/'动作来源.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n');print('airborne packs',len(overrides))
