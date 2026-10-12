"""Generated sprites only: copy/crop/resample and reversible background masks.
Does not modify runtime combat, movesets or released builds.
"""
from pathlib import Path
from PIL import Image
from scipy import ndimage as nd
import numpy as np
import json,base64,hashlib,statistics
P=Path(__file__).resolve().parent.parent;FX=P/'招式特效';ROOT=FX/'生图重做';OUT=ROOT/'实景预览';OUT.mkdir(exist_ok=True)
raw=(P/'候选试玩.html').read_text();game,_=json.JSONDecoder().raw_decode(raw.split('const DATA=',1)[1]);roster={c['id']:c for c in game['roster']}
manifest=json.loads((ROOT/'续批/任务.json').read_text());specs={j['id']:j for j in manifest['jobs']};selection=json.loads((FX/'确认名单.json').read_text());records={}
def uri(p):return 'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
casters={'flamethrower':6,'fireblast':6,'firepunch':68,'flamewheel':4,'watergun':7,'bubble':7,'hydropump':9,'surf':9,'aquajet':7,'vinewhip':3,'razorleaf':3,'solarbeam':3,'leafblade':470,'thunderbolt':25,'thunderpunch':68,'wildcharge':25,'icebeam':9,'blizzard':144,'iceshard':144,'iciclecrash':471,'airslash':6,'aerialace':21,'bravebird':146,'brickbreak':68,'closecombat':68,'aurasphere':448,'drainpunch':448,'earthquake':95,'earthpower':95,'bonerush':448,'rockslide':95,'stoneedge':95,'powergem':151,'shadowball':94,'phantomforce':94,'hex':94,'psychic':150,'psychocut':150,'agility':25,'irontail':25,'flashcannon':9,'poisonsting':92,'sludgebomb':94,'poisongas':92,'bugbite':123,'signalbeam':135,'dragonbreath':149,'dragonclaw':6,'dracometeor':149,'crunch':130,'darkpulse':197,'moonblast':700,'dazzlinggleam':700,'quickattack':25,'hyperbeam':143,'protect':7,'recover':65}
# The preview actor is not an assignment of a learnable move.
needs_learnset_review={'flamewheel','iciclecrash','poisonsting','poisongas'}

def clean_background(path,id):
    original=Image.open(path).convert('RGBA');a=np.array(original);method='original_alpha'
    if a[:,:,3].min()>0:
        rgb=a[:,:,:3].astype(np.int16);chroma=rgb.max(2)-rgb.min(2)
        black=np.median(rgb[:80,:80])<30
        if black:
            # Alpha extraction only; every RGB pixel is retained unchanged.
            mask=rgb.max(2)>22;method='black_background_alpha_mask'
        else:
            seed=chroma>17
            seed=nd.binary_closing(seed,structure=np.ones((3,3)))
            labels,n=nd.label(~seed);counts=np.bincount(labels.ravel());border=np.unique(np.concatenate([labels[0],labels[-1],labels[:,0],labels[:,-1]]));holes=(counts<18000);holes[border]=False;holes[0]=False
            mask=seed|holes[labels];method='neutral_checker_background_alpha_mask'
        a[:,:,3]=np.where(mask,255,0).astype('uint8');clean=Image.fromarray(a);assert np.array_equal(np.array(clean)[:,:,:3],np.array(original)[:,:,:3])
        clean.save(OUT/f'{id}-去底.png');method_note='本地仅提取透明蒙版；保留原RGB和原图，浅色边缘仍需目检。'
    else:clean=original;method_note='原始生图自带透明通道。'
    return clean,method,method_note

def atlas_for(id,j,path):
    im,method,note=clean_background(path,id);w,h=im.size;cells=[]
    for row in range(2):
        for col in range(2):cells.append(im.crop((col*w//2,row*h//2,(col+1)*w//2,(row+1)*h//2)))
    boxes=[c.getchannel('A').point(lambda v:255 if v>=80 else 0).getbbox() for c in cells];assert all(boxes),id
    anchor=j['anchor'];points=[]
    union=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
    for c,b in zip(cells,boxes):
        if j['shape'] in ('stream','arc'):
            arr=np.array(c.getchannel('A'));ys,xs=np.where(arr[:,b[0]+4:min(b[0]+20,b[2])]>=128);y=round(float(np.median(ys))) if len(ys) else (b[1]+b[3])//2;p=(b[0],y)
        elif anchor=='left':p=(union[0],(union[1]+union[3])//2)
        elif anchor=='right':p=(union[2],(union[1]+union[3])//2)
        elif anchor=='bottom':p=((union[0]+union[2])//2,union[3])
        else:p=((union[0]+union[2])//2,(union[1]+union[3])//2)
        points.append(p)
    left=max(x-b[0] for (x,y),b in zip(points,boxes))+3;right=max(b[2]-x for (x,y),b in zip(points,boxes))+3;top=max(y-b[1] for (x,y),b in zip(points,boxes))+3;bottom=max(b[3]-y for (x,y),b in zip(points,boxes))+3
    fw,fh=left+right,top+bottom;factor=min(1,384/max(fw,fh));dw,dh=max(1,round(fw*factor)),max(1,round(fh*factor));sheet=Image.new('RGBA',(dw,dh*4))
    for i,(c,(x,y)) in enumerate(zip(cells,points)):
        crop=c.crop((x-left,y-top,x+right,y+bottom)).resize((dw,dh),Image.Resampling.NEAREST);sheet.paste(crop,(0,i*dh))
    output=OUT/f'{id}-动画.png';sheet.save(output,optimize=True)
    records[id]={'original':str(path.relative_to(P)),'originalSHA256':sha(path),'processing':method,'note':note,'originalCellBounds':boxes,'sourceAnchors':points,'output':str(output.relative_to(P)),'outputSHA256':sha(output),'frameSize':[dw,dh],'opaquePixels':sum(v for v in sheet.getchannel('A').histogram()[1:]),'humanApproved':id in ('flamethrower','watergun')}
    return {'src':uri(output),'fw':dw,'fh':dh,'ax':left*dw/fw,'ay':top*dh/fh,'needsEdgeReview':method!='original_alpha'}

jobs={}
for id,move in selection['moves'].items():
    if id in specs:j=dict(specs[id]);path=ROOT/'续批'/f"{j['order']:02d}-{j['name']}"/'原始生图.png'
    else:
        j={'name':move['name'],'shape':'stream','anchor':'left','displaySizePx':[170,25] if id=='flamethrower' else [140,8],'trialRangePx':170 if id=='flamethrower' else 140,'trialSpeedPxPerSecond':125 if id=='flamethrower' else 105,'attachment':'从嘴部连续喷出，释放方向固定，不追踪。','subject':'短程火舌' if id=='flamethrower' else '细水柱','frames':'四帧连续喷射'};path=ROOT/'首批'/j['name']/'result.png'
    frame=atlas_for(id,j,path);shape=j['shape'];mode='shot'
    if shape in ('stream','arc'):mode='stream'
    elif id in ['flamewheel','aquajet','wildcharge','aerialace','bravebird','phantomforce','quickattack']:mode='rush'
    elif id in ['protect','recover','agility']:mode='support'
    elif id=='dazzlinggleam':mode='selfarea'
    elif shape in ('attachment','whip','held-prop'):mode='melee'
    elif shape=='falling-object':mode='fall'
    elif shape in ('ground-field','target-field'):mode='ground' if id!='earthquake' else 'selfarea'
    elif shape in ('ground-wave','wind-field','cloud'):mode='wave'
    reach=j['trialRangePx'];speed=j['trialSpeedPxPerSecond'] or 100
    duration=reach/speed if mode in ('shot','stream','rush','wave') else 1.25 if mode in ('ground','fall','selfarea','support') else .85
    width,height=j['displaySizePx']
    jobs[id]={'id':id,'name':j['name'],'type':move['type'],'color':move['color'],'shape':shape,'anchor':j['anchor'],'mode':mode,'caster':casters[id],'reach':reach,'speed':speed,'duration':max(.65,duration),'windup':.75,'hold':.5 if mode=='stream' else 0,'rest':1.1,'fade':.3,'width':width,'height':height,'attachment':j['attachment'],'note':j['subject'],'learnsetWarning':id in needs_learnset_review,'original':str(path.relative_to(P)),**frame}
# Frozen candidate scales only: species-size/stat research is separate and not applied here.
scene={'environment':game['environment'],'ground':uri(P/game['environment']['groundSrc']),'objects':uri(P/game['environment']['objectsSrc']),'target':68,'characters':{}}
for id in sorted(set(casters.values())|{68}):
    arts={k:dict(v) for k,v in game['art'][str(id)].items() if k in ('idle','walk','shoot','melee','hurt','dash')}
    for role,a in arts.items():
        image=Image.open(P/a['src']).convert('RGBA');row=0 if a['rows']==1 else 6;points=[];centers=[];bottoms=[]
        for n in range(a['frames']):
            f=image.crop((n*a['frameWidth'],row*a['frameHeight'],(n+1)*a['frameWidth'],(row+1)*a['frameHeight']));mask=np.array(f.getchannel('A'))>128;ys,xs=np.where(mask);assert len(xs)
            box=(int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max()));centers.append([(box[0]+box[2])/2,(box[1]+box[3])/2]);bottoms.append([(box[0]+box[2])/2,box[3]])
            # Front edge in upper body band follows the native animation, not a fixed world offset.
            band=mask.copy();band[:box[1]+round((box[3]-box[1])*.12)]=False;band[box[1]+round((box[3]-box[1])*.72)+1:]=False
            yy,xx=np.where(band)
            if len(xx):edge=xx.max();frontys=yy[xx>=edge-1];points.append([int(edge),float(np.median(frontys))])
            else:points.append([box[2],(box[1]+box[3])/2])
        a['frontPoints']=points;a['centerPoints']=centers;a['bottomPoints']=bottoms;a['src']=uri(P/a['src'])
    scene['characters'][str(id)]={'meta':roster[id],'art':arts}
# Explicit exceptions where body-front is not the actual emission point.
for id in ['flamethrower','fireblast']:jobs[id].update(poseFrame=5,emitLocal=[53,27])
jobs['watergun'].update(poseFrame=5,emitLocal=[28,16])
for id in ['hydropump','icebeam','flashcannon']:jobs[id].update(poseFrame=3,emitLocal=[34,21])
for id,note in {'hyperbeam':'当前生图偏火舌，是否需要更像凝聚光束，待你确认。','icebeam':'当前冰冻光束仍偏水流形状，霜晶识别性待确认。','drainpunch':'原图含实体拳头，可能和原角色的拳头重叠；本招仍需修整。','bravebird':'能量羽翼可能遮住原角色，贴合与比例待验收。'}.items():jobs[id]['reviewNote']=note
jobs['solarbeam']['emit']='top';jobs['vinewhip']['emit']='body';jobs['bonerush']['emit']='hand';jobs['irontail']['emit']='tail'
style=(P/'招式特效展台模板.html').read_text().split('<style>',1)[1].split('</style>',1)[0]
payload={'moves':jobs,'types':selection['types']}
html=(FX/'生图全招模板.html').read_text().replace('__STYLE__',style).replace('__DATA__',json.dumps(payload,ensure_ascii=False)).replace('__SCENE__',json.dumps(scene,ensure_ascii=False)).replace('__JS__',(FX/'生图全招预览.js').read_text())
output=P/'招式重做-57招生图实景.html';output.write_text(html)
report={'state':'built_pending_checks','output':str(output),'count':len(jobs),'generatedOriginals':57,'masksApplied':sum(v['processing']!='original_alpha' for v in records.values()),'sha256':sha(output),'sourceCandidateSHA256':sha(P/'候选试玩.html'),'assets':records,'formalBattleChanged':False,'gameStatsChanged':False,'limitations':['独立演示，不是正式伤害判定或配招。','临时演示角色不是学招白名单；标记招式未确认50名中可用角色。','13张灰棋盘/黑底的局部抠底需看边缘。','原生动作锚点为预览对齐，不等于八方向逐帧人工验收完成。']}
(OUT/'构建记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='assets'},ensure_ascii=False))
