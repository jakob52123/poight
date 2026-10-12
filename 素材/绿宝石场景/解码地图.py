"""Pinned pret/pokeemerald maps -> lossless raster layers + original grid fields.
No ROM, generation API, upstream game code execution, or network at build time.
"""
from pathlib import Path
from functools import lru_cache
import hashlib, json, re, struct, subprocess
from PIL import Image
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'原始/pokeemerald'
OUT=ROOT/'解码'; PIN='731ad5bfd6e6f265508d0efcca0ba42f9dcf5881'
sha=lambda b:hashlib.sha256(b).hexdigest()
inputs={}; unloaded_tiles=set()
def raw(path):
 p=SRC/path; b=p.read_bytes(); inputs[str(path)]={'bytes':len(b),'sha256':sha(b)};return b
def text(path):return raw(path).decode()
def words(path):
 b=raw(path);assert len(b)%2==0;return struct.unpack('<'+'H'*(len(b)//2),b)
def read_defs():
 headers=text('src/data/tilesets/headers.h'); graphics=text('src/data/tilesets/graphics.h')+'\n'+text('src/graphics.c'); meta=text('src/data/tilesets/metatiles.h')
 definitions={}
 for name,body in re.findall(r'const struct Tileset (\w+)\s*=\s*\{(.*?)\};',headers,re.S):
  fields=dict(re.findall(r'\.(\w+)\s*=\s*(\w+)',body));definitions[name]=fields
 paths=dict(re.findall(r'const \w+ (\w+)\[.*?=\s*INC(?:GFX|BIN)_\w+\("([^"]+)"',graphics+'\n'+meta))
 pals={name:re.findall(r'"([^"]+\.pal)"',body) for name,body in re.findall(r'const u16 (\w+)\[\]\[16\]\s*=\s*\{(.*?)\};',graphics,re.S)}
 return definitions,paths,pals
DEFS,PATHS,PALS=read_defs()
@lru_cache(None)
def palette(path):
 s=text(path).splitlines();assert s[:3]==['JASC-PAL','0100','16'];c=[tuple(map(int,x.split())) for x in s[3:] if x.strip()];assert len(c)==16;return c
@lru_cache(None)
def tileset(name):
 d=DEFS[name];path=PATHS[d['tiles']];raw(path)
 im=Image.open(SRC/path);assert im.mode=='P' and im.width%8==0 and im.height%8==0 and im.getextrema()[1]<16,(name,im.mode)
 return {'tiles':im.copy(),'palettes':[palette(p) for p in PALS[d['palettes']]],'meta':words(PATHS[d['metatiles']]),'attributes':words(PATHS[d['metatileAttributes']])}
@lru_cache(18000)
def tile(primary,secondary,word):
 p,s=tileset(primary),tileset(secondary);idx=word&1023;pi=word>>12
 assert pi<16,(primary,secondary,pi)  # Source supplies all 16 slots; preserve scripted palette slots too.
 src=p if idx<512 else s; idx=idx if idx<512 else idx-512
 im=src['tiles']; cols=im.width//8
 if idx>=im.width*im.height//64:
  unloaded_tiles.add((primary,secondary,word));return Image.new('RGBA',(8,8))
 pal=(p if pi<6 else s)['palettes'][pi]
 cut=im.crop((idx%cols*8,idx//cols*8,idx%cols*8+8,idx//cols*8+8));out=Image.new('RGBA',(8,8))
 out.putdata([(*pal[i],255 if i else 0) for i in cut.get_flattened_data()])
 if word&0x400:out=out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
 if word&0x800:out=out.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
 return out
@lru_cache(9000)
def metatile(primary,secondary,id):
 src=tileset(primary if id<512 else secondary);idx=id if id<512 else id-512
 assert idx<len(src['attributes']) and idx*8+8<=len(src['meta']),(primary,secondary,id)
 attr=src['attributes'][idx];kind=attr>>12;assert kind in (0,1,2),(id,kind)
 lower=Image.new('RGBA',(16,16));upper=Image.new('RGBA',(16,16))
 for n,w in enumerate(src['meta'][idx*8:idx*8+8]):
  (lower if n<4 else upper).alpha_composite(tile(primary,secondary,w),(n%2*8,n%4//2*8))
 # include/global.fieldmap.h enum: NORMAL=0,COVERED=1,SPLIT=2.
 # BG1 covers actor sprites; COVERED places both layers below actor sprites.
 if kind==1:lower.alpha_composite(upper);upper=Image.new('RGBA',(16,16))
 return lower,upper,attr

def write_json(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def decode(layout):
 name=layout['name'];p=layout['primary_tileset'];s=layout['secondary_tileset'];w,h=layout['width'],layout['height'];blocks=words(layout['blockdata_filepath']);assert len(blocks)>=w*h and (len(blocks)==w*h or len(blocks)==w*h+1 and blocks[-1]==0),(name,'block count',len(blocks),w*h)
 blocks=blocks[:w*h]  # Upstream unused 1x1 layouts may include one zero alignment word.
 g=Image.new('RGBA',(w*16,h*16),(*tileset(p)['palettes'][0][0],255));u=Image.new('RGBA',g.size)
 collision=[];elevations=[];behaviors=[];layers=[]
 for i,v in enumerate(blocks):
  lo,hi,attr=metatile(p,s,v&1023);xy=(i%w*16,i//w*16);g.alpha_composite(lo,xy);u.alpha_composite(hi,xy)
  collision.append((v>>10)&3);elevations.append(v>>12);behaviors.append(attr&255);layers.append(attr>>12)
 OUT.mkdir(exist_ok=True)
 paths={}
 for suffix,im in [('ground',g),('over',u)]:
  path=OUT/f'{name}-{suffix}.png';im.save(path,optimize=True);b=path.read_bytes();paths[suffix]={'path':str(path.relative_to(ROOT)),'sha256':sha(b),'bytes':len(b)}
 row={'id':layout['id'],'name':name,'width':w,'height':h,'primary':p,'secondary':s,'layers':paths,'collision':collision,'elevation':elevations,'behavior':behaviors,'layerType':layers,'blockSHA256':sha(raw(layout['blockdata_filepath']))}
 write_json(OUT/f'{name}.json',row)
 return row

def main():
 commit=subprocess.check_output(['git','-C',str(SRC),'rev-parse','HEAD'],text=True).strip();assert commit==PIN,(commit,PIN)
 dirty=subprocess.check_output(['git','-C',str(SRC),'status','--porcelain'],text=True);assert not dirty,'upstream source modified'
 constants=text('include/global.fieldmap.h');assert re.findall(r'\b(METATILE_LAYER_TYPE_\w+)\s*,',constants)==['METATILE_LAYER_TYPE_NORMAL','METATILE_LAYER_TYPE_COVERED','METATILE_LAYER_TYPE_SPLIT']
 layouts=json.loads(text('data/layouts/layouts.json'))['layouts'];results=[];errors=[]
 # Decode referenced maps first; all layout failures are preserved, never silently dropped.
 maps=[json.loads(text(str(p.relative_to(SRC)))) for p in sorted((SRC/'data/maps').glob('*/map.json'))]
 for i,l in enumerate(layouts):
  try:r=decode(l);results.append({k:v for k,v in r.items() if k not in ('collision','elevation','behavior','layerType')})
  except Exception as e:errors.append({'layout':l['id'],'error':str(e),'type':type(e).__name__})
  if (i+1)%50==0:print(f'decoded {i+1}/{len(layouts)} errors={len(errors)}',flush=True)
 available={r['id'] for r in results}
 for m in maps:m['decoded']=m['layout'] in available
 write_json(ROOT/'地图索引.json',{'sourceCommit':PIN,'maps':maps,'layouts':results,'errors':errors})
 write_json(ROOT/'来源核验.json',{'source':'https://github.com/pret/pokeemerald','commit':PIN,'romRead':False,'paidAPICalls':0,'generatedArt':False,'totalMaps':len(maps),'decodedMaps':sum(m['decoded'] for m in maps),'totalLayouts':len(layouts),'decodedLayouts':len(results),'errors':errors,'unloadedTileWords':sorted(unloaded_tiles),'unloadedTilePolicy':'Transparent zero VRAM; visibility must be checked separately, not invented replacement pixels','files':inputs,'limitations':['Static first-frame tiles only; tileset animation/palette cycling omitted','Original collision/elevation/behavior preserved as data; this decoder does not claim runtime behavior parity','Original NPC/event/script/warp semantics not executed','Public decompilation availability is not copyright clearance']})
 print(json.dumps({'maps':len(maps),'decodedMaps':sum(m['decoded'] for m in maps),'layouts':len(results),'errors':errors},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
