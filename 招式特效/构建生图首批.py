"""Crop actual generated PNGs into aligned frames; no procedural effect drawing."""
from pathlib import Path
from PIL import Image
import json,base64,hashlib,statistics
P=Path(__file__).resolve().parent.parent;OUT=P/'招式特效/生图重做/首批';scene_dir=P/'招式特效'
raw=(P/'候选试玩.html').read_text();game,_=json.JSONDecoder().raw_decode(raw.split('const DATA=',1)[1]);roster={c['id']:c for c in game['roster']}
def uri(path):return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
fx={};receipts={}
for id,name,reach,speed,caster,muzzle in [('flamethrower','喷射火焰',170,125,6,[53,27]),('watergun','水枪',140,105,7,[28,16])]:
    source=OUT/name/'result.png';im=Image.open(source).convert('RGBA');w,h=im.size;assert w%2==0 and h%2==0
    crops=[];meta=[]
    for row in range(2):
        for col in range(2):
            frame=im.crop((col*w//2,row*h//2,(col+1)*w//2,(row+1)*h//2));alpha=frame.getchannel('A');box=alpha.point(lambda v:255 if v>=64 else 0).getbbox();assert box
            # Locate the nozzle in the narrow leftmost part of the generated stream.
            ys=[]
            for y in range(box[1],box[3]):
                if any(alpha.getpixel((x,y))>=128 for x in range(box[0]+8,min(box[0]+24,box[2]))):ys.append(y)
            root_y=round(statistics.median(ys));root_x=box[0];meta.append({'sheetCell':[col,row],'opaqueBounds':list(box),'root':[root_x,root_y]});crops.append((frame,box,root_x,root_y))
    width=max(box[2]-x for _,box,x,y in crops)+3;above=max(y-box[1] for _,box,x,y in crops)+3;below=max(box[3]-y for _,box,x,y in crops)+3;height=above+below
    sheet=Image.new('RGBA',(width,height*4),(0,0,0,0))
    for i,(frame,box,x,y) in enumerate(crops):
        # Raster copy only: no drawing, invented particles, recolouring, or generated fallback.
        crop=frame.crop((x,max(0,y-above),x+width,min(frame.height,y+below)));sheet.paste(crop,(0,i*height+max(0,above-y)))
    sheetpath=OUT/name/'对齐动画.png';sheet.save(sheetpath)
    originals=[hashlib.sha256(source.read_bytes()).hexdigest()];record=json.loads((OUT/name/'任务记录.json').read_text())
    receipts[id]={'name':name,'original':str(source),'originalSHA256':originals[0],'route':record['route'],'nativeSource':record.get('recoveredFrom'),'processing':'crop and align original raster frames only; no effect painting','cells':meta,'frameSize':[width,height],'alphaExtrema':sheet.getchannel('A').getextrema()}
    fx[id]={'id':id,'name':name,'caster':caster,'reach':reach,'speed':speed,'windup':.75,'hold':.65,'fade':.35,'rest':1.1,'frameWidth':width,'frameHeight':height,'anchorY':above,'muzzle':muzzle,'poseFrame':4,'src':uri(sheetpath)}
D={'environment':game['environment'],'ground':uri(P/game['environment']['groundSrc']),'objects':uri(P/game['environment']['objectsSrc']),'casters':{k:v['caster'] for k,v in fx.items()},'target':68,'characters':{}}
for n in [6,7,68]:
    arts={k:dict(v) for k,v in game['art'][str(n)].items() if k in ('idle','walk','shoot','hurt')}
    for a in arts.values():a['src']=uri(P/a['src'])
    D['characters'][str(n)]={'meta':roster[n],'art':arts}
js=(scene_dir/'真实场景.js').read_text().replace("let current='bravebird'","let current='flamethrower'")
style=(P/'招式特效展台模板.html').read_text().split('<style>',1)[1].split('</style>',1)[0]
html=(scene_dir/'生图首批模板.html').read_text().replace('__STYLE__',style).replace('__SPRITE_DATA__',json.dumps(fx,ensure_ascii=False)).replace('__SCENE_DATA__',json.dumps(D,ensure_ascii=False)).replace('__SCENE_JS__',js)
output=P/'招式重做-生图首批.html';output.write_text(html)
report={'count':2,'output':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size,'assets':receipts,'status':'built_pending_browser_and_human_review','formalBattleChanged':False}
(OUT/'集成记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({'output':str(output),'bytes':report['bytes'],'sha256':report['sha256']},ensure_ascii=False))
