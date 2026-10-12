"""有界整理全国图鉴1–1025的可用原生像素动作。失败物种不计入可玩数；无生成API。"""
from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor,as_completed
from PIL import Image
from io import BytesIO,StringIO
import csv,hashlib,json,math,time,os,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent;RAW=ROOT/'原始';RAW.mkdir(exist_ok=True)
BASE='https://raw.githubusercontent.com/PMDCollab/SpriteCollab/7f6ea6cc6892bbdd1376f803b3a1d7f376418895/sprite/'
STATUS=ROOT/'进度.json';ORDER=[0,7,6,5,4,3,2,1];TARGET=min(1025,int(os.environ.get('POCKET_ROSTER_LIMIT','1025')))

def get(url,path):
    if path.exists() and path.stat().st_size: return path.read_bytes()
    last=None
    for attempt in range(2):
        try:
            with urlopen(Request(url,headers={'User-Agent':'pocket-personal-prototype/1'}),timeout=18) as r:data=r.read(3000000)
            if len(data)>=3000000:raise ValueError('Unexpected file size')
            path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.part');tmp.write_bytes(data);tmp.replace(path);return data
        except Exception as e:
            last=e
            if '403' in str(e) or '404' in str(e) or 'Operation not permitted' in str(e):break
            time.sleep(.3)
    raise last

def pokedata(name):
    url='https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'+name+'.csv'
    return list(csv.DictReader(StringIO(get(url,RAW/(name+'.csv')).decode())))

species=pokedata('pokemon_species_names');names={int(r['pokemon_species_id']):r['name'] for r in species if r['local_language_id']=='12'}
types={}
for r in pokedata('pokemon_types'):
    n=int(r['pokemon_id'])
    if 1<=n<=TARGET:types.setdefault(n,[]).append(int(r['type_id']))
stats={}
for r in pokedata('pokemon_stats'):
    n=int(r['pokemon_id'])
    if 1<=n<=TARGET:stats.setdefault(n,{})[int(r['stat_id'])]=int(r['base_stat'])

def process(n):
    cached=ROOT/f'{n:04}/角色.json'
    if cached.exists():
        previous=json.loads(cached.read_text())
        if all((ROOT/a['file']).exists() for a in previous['art'].values()):return previous
    path=RAW/f'{n:04}';base=BASE+f'{n:04}/';receipts=[]
    def pull(name):
        data=get(base+name,path/name);receipts.append({'file':name,'url':base+name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()});return data
    xml=pull('AnimData.xml');credits=pull('credits.txt').decode('utf-8-sig')
    nodes={a.findtext('Name'):a for a in ET.fromstring(xml).findall('.//Anim')}
    def resolve(name):
        seen=set()
        while nodes[name].findtext('CopyOf'):
            if name in seen:raise ValueError('animation alias cycle')
            seen.add(name);name=nodes[name].findtext('CopyOf')
        return name
    choices={'idle':['Idle','Walk'],'walk':['Walk','Idle'],'shoot':['Shoot','SpAttack','Attack'],'melee':['Attack','Strike','Swing'],'hurt':['Pain','Hurt','Idle'],'dash':['Tumble','Hop','Walk']}
    art={};audits={};cache={};native_actions={};thumb=None
    for key,candidates in choices.items():
        original=next((c for c in candidates if c in nodes),None)
        if not original:raise ValueError('Missing '+key)
        name=resolve(original)
        if name in native_actions:art[key]={**native_actions[name],'roleFallback':original!=candidates[0]};continue
        a=nodes[name];fw=int(a.findtext('FrameWidth'));fh=int(a.findtext('FrameHeight'));ticks=[int(x.text) for x in a.findall('Durations/Duration')];frames=len(ticks)
        if not frames or any(t<=0 for t in ticks):raise ValueError('bad duration')
        image=Image.open(BytesIO(pull(name+'-Anim.png'))).convert('RGBA');shadow=Image.open(BytesIO(pull(name+'-Shadow.png'))).convert('RGBA')
        assert image.size==shadow.size and image.width==fw*frames and image.height%fh==0
        rows=image.height//fh;assert rows in (1,8)
        order=ORDER if rows==8 else [0];cells=[];bounds=[];unique=[];frame_variation=[]
        for sr in order:
            first=shadow.crop((0,sr*fh,fw,(sr+1)*fh));white=[(x,y) for y in range(fh) for x in range(fw) if first.getpixel((x,y))==(255,255,255,255)]
            if len(white)!=1:raise ValueError(f'{name}: ambiguous root {len(white)}')
            rx,ry=white[0];poses=set();full_frames=set()
            for f in range(frames):
                cell=image.crop((f*fw,sr*fh,(f+1)*fw,(sr+1)*fh));box=cell.getbbox()
                if not box:raise ValueError(f'{name}: empty frame')
                bounds.append((box[0]-rx,box[1]-ry,box[2]-rx,box[3]-ry));cells.append((cell,rx,ry));poses.add(hashlib.sha256(cell.crop(box).tobytes()).hexdigest());full_frames.add(hashlib.sha256(cell.tobytes()).hexdigest())
            unique.append(len(poses));frame_variation.append(len(full_frames))
        loX=min(b[0] for b in bounds);loY=min(b[1] for b in bounds);hiX=max(b[2] for b in bounds);hiY=max(b[3] for b in bounds)
        cw=math.ceil((hiX-loX+4)/2)*2;ch=math.ceil((hiY-loY+4)/2)*2;ax=2-loX;ay=2-loY
        assert 0<cw<=256 and 0<ch<=256
        atlas=Image.new('RGBA',(cw*frames,ch*rows))
        for index,(cell,rx,ry) in enumerate(cells):
            tile=Image.new('RGBA',(cw,ch));tile.paste(cell,(ax-rx,ay-ry));box=tile.getbbox()
            assert box and 0<box[0]<box[2]<cw and 0<box[1]<box[3]<ch
            # Root-relative visible pixels are retained, including native displacement.
            assert sum(v>0 for v in cell.getchannel('A').get_flattened_data())==sum(v>0 for v in tile.getchannel('A').get_flattened_data())
            atlas.paste(tile,(index%frames*cw,index//frames*ch))
        out=ROOT/f'{n:04}';out.mkdir(exist_ok=True);file=out/(name+'.png');atlas.save(file,optimize=True)
        hit=a.findtext('HitFrame');hit=int(hit) if hit is not None else None
        if hit is not None:assert 0<=hit<frames
        item={'file':str(file.relative_to(ROOT)),'frameWidth':cw,'frameHeight':ch,'frames':frames,'rows':rows,'anchorX':ax,'anchorY':ay,'durations':[t/60 for t in ticks],'totalDuration':sum(ticks)/60,'hitFrame':hit,'hitTime':sum(ticks[:hit])/60 if hit is not None else None,'sourceAnimation':name,'roleFallback':original!=candidates[0]}
        art[key]=item;native_actions[name]=item;audits[name]={'rows':rows,'frames':frames,'distinctPoses':unique,'distinctFullFrames':frame_variation,'pixelCountPreserved':True,'clippedFrames':0,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
        if key=='idle':
            first=cells[0][0];box=first.getbbox();thumb=first.crop(box);thumb.thumbnail((42,42),Image.Resampling.NEAREST);icon=Image.new('RGBA',(48,48));icon.paste(thumb,((48-thumb.width)//2,(48-thumb.height)//2),thumb);icon.save(out/'icon.png',optimize=True)
            body_height=box[3]-box[1]
    walk_audit=audits[art['walk']['sourceAnimation']]
    # 已人工检查少帧目检.png：未知图腾/茧/悬浮物种有真实原生位移帧，不伪称有步态。
    # 接纳原生浮动序列，但不接纳只有一张静图的假走路。
    if min(walk_audit['distinctFullFrames'])<2:raise ValueError('Walk has only one distinct full frame')
    native_float=min(walk_audit['distinctPoses'])<2
    (path/'来源.json').write_text(json.dumps({'files':receipts,'credits':credits},ensure_ascii=False,indent=2)+'\n')
    # These are readable arcade rules, explicitly not the original turn-based damage formula.
    hp=round(max(90,min(135,95+(stats[n][1]-50)*.22)))
    speed=round(max(158,min(214,175+(stats[n][6]-50)*.38)))
    size=max(.75,min(2,round(52/body_height*4)/4))
    result={'id':n,'name':names.get(n,f'#{n:03}'),'types':types[n],'hp':hp,'speed':speed,'scale':size,'art':art,'icon':f'{n:04}/icon.png','credits':credits,'audit':audits,'nativeFloatOrBob':native_float}
    (ROOT/f'{n:04}/角色.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

start=time.monotonic();results={};errors={};selected=os.environ.get('POCKET_ROSTER_IDS')
if selected:
    results={c['id']:c for c in json.loads((ROOT/'角色库.json').read_text())}
    errors={int(k):v for k,v in json.loads(STATUS.read_text())['failed'].items()}
    ids=[int(n) for n in selected.split(',')]
else:ids=list(range(1,TARGET+1))
STATUS.write_text(json.dumps({'state':'running','target':TARGET,'done':len(results)}))
with ThreadPoolExecutor(max_workers=6) as ex:
    jobs={ex.submit(process,n):n for n in ids if n in names and n in types and n in stats}
    for f in as_completed(jobs):
        n=jobs[f]
        try:results[n]=f.result();errors.pop(n,None);print(n,results[n]['name'],'OK',flush=True)
        except Exception as e:errors[n]=repr(e);print(n,'FAIL',repr(e),flush=True)
        STATUS.write_text(json.dumps({'state':'running','target':TARGET,'done':len(results),'failed':errors,'seconds':round(time.monotonic()-start)},ensure_ascii=False,indent=2))
(ROOT/'角色库.json').write_text(json.dumps([results[n] for n in sorted(results)],ensure_ascii=False,separators=(',',':'))+'\n')
STATUS.write_text(json.dumps({'state':'completed','target':TARGET,'done':len(results),'failed':errors,'seconds':round(time.monotonic()-start,2)},ensure_ascii=False,indent=2)+'\n')
