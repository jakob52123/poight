from PIL import Image,ImageDraw
from pathlib import Path
import xml.etree.ElementTree as ET
import hashlib,json
P=Path('原始'); directions=['S','SW','W','NW','N','NE','E','SE']; order=[0,7,6,5,4,3,2,1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(p,o):Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
nodes={a.findtext('Name'):a for a in ET.parse(P/'AnimData.xml').findall('.//Anim')}
pack={'directions':directions,'actions':{}}
audit={'directionCheck':{'sourceRows':['S','SE','E','NE','N','NW','W','SW'],'outputToSourceRows':order,'method':'逐行目检头脸、龟壳与尾巴朝向；方向目检.png'},'sourceSHA':[], 'actions':{}}
for e in json.loads((P/'来源.json').read_text()):
 ok=sha((P/e['file']).read_bytes())==e['sha256'];assert ok;audit['sourceSHA'].append({'file':e['file'],'match':ok})
compare=Image.new('RGB',(1000,6*210),(232,234,238)); draw=ImageDraw.Draw(compare)
# 父级验收：Hurt/Charge姿态过少，改用Pain与真实Tumble序列；不伪称Tumble有8方向。
for ai,(key,name) in enumerate(dict(idle='Idle',walk='Walk',shoot='Shoot',melee='Attack',hurt='Pain',dash='Tumble').items()):
 a=nodes[name];w=int(a.findtext('FrameWidth'));h=int(a.findtext('FrameHeight'));ticks=[int(x.text) for x in a.findall('Durations/Duration')];n=len(ticks)
 im=Image.open(P/f'{name}-Anim.png').convert('RGBA');shadow=Image.open(P/f'{name}-Shadow.png').convert('RGBA');offset=Image.open(P/f'{name}-Offsets.png').convert('RGBA');native_rows=im.height//h;assert native_rows in (1,8);assert im.size==shadow.size==offset.size==(w*n,h*native_rows)
 output_order=order if native_rows==8 else [0]
 atlas=Image.new('RGBA',(96*n,96*native_rows)); records=[];rows=[];refs=[]
 for r,sr in enumerate(output_order):
  centers=[]
  for f in range(n):
   points=[(x,y) for y in range(h) for x in range(w) if shadow.getpixel((f*w+x,sr*h+y))==(255,255,255,255)]
   assert len(points)==1;centers.append(points[0])
  ref=centers[0];refs.append(ref);dx,dy=48-ref[0],64-ref[1];framehash=[];shapehash=[]
  for f in range(n):
   src=im.crop((f*w,sr*h,(f+1)*w,(sr+1)*h));bb=src.getbbox();assert bb
   dest=(bb[0]+dx,bb[1]+dy,bb[2]+dx,bb[3]+dy);assert 0<dest[0]<dest[2]<96 and 0<dest[1]<dest[3]<96
   tile=Image.new('RGBA',(96,96));tile.paste(src,(dx,dy));atlas.paste(tile,(f*96,r*96))
   assert tile.crop((dx,dy,dx+w,dy+h)).tobytes()==src.tobytes()
   opaque=sum(v>0 for v in tile.getchannel('A').getdata());assert opaque==sum(v>0 for v in src.getchannel('A').getdata())
   fh=sha(tile.tobytes());framehash.append(fh);shapehash.append(sha(src.crop(bb).tobytes()))
   records.append({'row':r,'direction':directions[r],'frame':f,'rgbaBounds':dest,'visiblePixels':opaque,'alphaExtrema':tile.getchannel('A').getextrema(),'sha256':fh,'sourceShadow':centers[f],'outputShadow':[centers[f][0]+dx,centers[f][1]+dy],'pixelExact':True,'clipped':False})
  rows.append({'direction':directions[r],'uniqueFrameHashes':len(set(framehash)),'uniquePoseHashesIgnoringTranslation':len(set(shapehash)),'sha256':sha(atlas.crop((0,r*96,n*96,(r+1)*96)).tobytes())})
 atlas.save(key+'.png'); hit=a.findtext('HitFrame');hit=int(hit) if hit is not None else None
 pack['actions'][key]={'file':key+'.png','frameWidth':96,'frameHeight':96,'frames':n,'rows':native_rows,'anchorX':48,'anchorY':64,'durations':[t/60 for t in ticks],'hitFrame':hit,'hitTime':sum(ticks[:hit])/60 if hit is not None else None,'totalDuration':sum(ticks)/60,'sourceAnimation':name}
 audit['actions'][key]={'sourceFrameSize':[w,h],'sourceTicks':ticks,'sourceHitFrame':hit,'fixedSourceReferencePerOutputRow':refs,'nativeDisplacementPreserved':True,'rows':rows,'uniqueRowHashes':len(set(x['sha256'] for x in rows)),'frames':records,'atlasSHA256':sha(Path(key+'.png').read_bytes())}
 # Four samples from distinct actual poses where the source offers them.
 times=[0,sum(ticks)/60*.25,sum(ticks)/60*.5,sum(ticks)/60*.9];indices=[]
 for t in times:
  elapsed=0
  for f,d in enumerate(ticks):
   elapsed+=d/60
   if t<elapsed:break
  indices.append(f)
 if n>=4:indices=[0,n//3,2*n//3,n-1];times=[sum(ticks[:f])/60 for f in indices]
 draw.text((12,ai*210+6),f'{key} / {name} / W / 2x nearest',fill=(20,30,40))
 for c,(f,t) in enumerate(zip(indices,times)):
  sample_row=2 if native_rows==8 else 0
  tile=atlas.crop((f*96,sample_row*96,(f+1)*96,(sample_row+1)*96)).resize((192,192),Image.Resampling.NEAREST)
  compare.paste(tile,(155+c*210,ai*210),tile);draw.text((165+c*210,ai*210+188),f'f{f}  t={t:.4f}s',fill=(20,30,40))
 audit['actions'][key]['comparisonSamples']=[{'frame':f,'time':t} for f,t in zip(indices,times)]
compare.save('动作对照.png');save('动作包.json',pack)
# Reopen all delivered files to verify interface and dimensions.
reloaded=json.loads(Path('动作包.json').read_text());assert list(reloaded['actions'])==['idle','walk','shoot','melee','hurt','dash']
for key,a in reloaded['actions'].items():
 image=Image.open(a['file']);assert image.mode=='RGBA' and image.size==(a['frames']*a['frameWidth'],a['rows']*a['frameHeight']);assert len(a['durations'])==a['frames'];assert abs(sum(a['durations'])-a['totalDuration'])<1e-12
 if a['hitFrame'] is not None:assert abs(sum(a['durations'][:a['hitFrame']])-a['hitTime'])<1e-12
 # Pain原始8行只有3个不同方向序列；Tumble原始只有1行，不伪造方向。
 assert audit['actions'][key]['uniqueRowHashes']=={'hurt':3,'dash':1}.get(key,8)
 assert min(r['uniqueFrameHashes'] for r in audit['actions'][key]['rows'])>1
 assert min(r['uniquePoseHashesIgnoringTranslation'] for r in audit['actions'][key]['rows'])>1
print({k: [(r['uniqueFrameHashes'],r['uniquePoseHashesIgnoringTranslation']) for r in a['rows']] for k,a in audit['actions'].items()})
audit['summary']={'actions':6,'directions':8,'directionIndependentActions':['dash'],'totalCells':sum(a['frames']*a['rows'] for a in pack['actions'].values()),'clippedCells':0,'pixelExact':True,'metadataVerified':True,'sourceSHAMatches':len(audit['sourceSHA']),'frameIndexBase':0,'hitTimeConvention':'命中帧开始时刻；sum(durations[:hitFrame])','parentChanges':['hurt: Hurt改Pain；dash: Charge改Tumble，六类动作均验证不止一个独立姿态。'],'limitations':['Tumble原素材只有一行，是全方向共用翻滚序列，不是8方向独立动作。','Pain原始8行中只有3个不同方向序列，重复方向如实保留；每行有真实姿态变化。','Shoot仅角色动作，水柱由游戏绘制；Attack为原生近身撞击，非新增手刀。']}
save('动作验收.json',audit)
