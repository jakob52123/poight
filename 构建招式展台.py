"""57招独立离线HTML，严格名单；不修改正式游戏、配招或数值。"""
from pathlib import Path
import json,base64,subprocess,hashlib
ROOT=Path(__file__).resolve().parent
WORK=Path('/tmp/pocket-57-fx-20261011')
data=json.loads((ROOT/'招式特效/确认名单.json' if (ROOT/'招式特效/确认名单.json').exists() else WORK/'selection.json').read_text())
ids=set(data['moves']);assert len(ids)==57
assert not {'inferno','thunder','gust','lick'}&ids and 'aerialace' in ids
parts=[];receipts={};outdir=ROOT/'招式特效';outdir.mkdir(exist_ok=True)
for lane in ['ranged','contact','area']:
 path=WORK/lane;js=outdir/(lane+'.js')
 if not js.exists():
  status=json.loads((path/'status.json').read_text());assert status['state']=='complete' and status['rc']==0,(lane,status)
  js=path/'effects.js'
 subprocess.run(['node','--check',str(js)],check=True,capture_output=True)
 code=js.read_text();assert '</script' not in code.lower()
 (outdir/(lane+'.js')).write_text(code);parts.append(code);receipts[lane]={'sha256':hashlib.sha256(code.encode()).hexdigest(),'source':str(js)}
approved=(outdir/'勇鸟原型.js' if (outdir/'勇鸟原型.js').exists() else Path('/tmp/pocket-parallel-polish-20261011/effects/特效候选.js')).read_text()
(outdir/'勇鸟原型.js').write_text(approved)
for extra in ['勇鸟原型.js','整合修正.js','勇鸟适配.js']:
    subprocess.run(['node','--check',str(outdir/extra)],check=True,capture_output=True)
    parts.append((outdir/extra).read_text())
probe="global.window=global;"+''.join('require('+json.dumps(str(outdir/(lane+'.js')))+');' for lane in ['ranged','contact','area'])+''.join('require('+json.dumps(str(outdir/f))+');' for f in ['勇鸟原型.js','整合修正.js','勇鸟适配.js'])+'console.log(JSON.stringify(Object.keys(MoveFX)));'
registered=json.loads(subprocess.run(['node','-e',probe],check=True,capture_output=True,text=True).stdout)
assert set(registered)==ids,(set(registered)-ids,ids-set(registered))
air=ROOT/'素材/角色库/飞行修正';art=json.loads((air/'飞行包.json').read_text())['21']['art'];sprite=base64.b64encode((air/'0021-Air.png').read_bytes()).decode()
# Reuse the actual game's scene and curated character atlases, embedded for offline viewing.
raw=(ROOT/'候选试玩.html').read_text();start=raw.index('const DATA=')+len('const DATA=');game,_=json.JSONDecoder().raw_decode(raw[start:])
preferred={1:143,2:448,3:21,4:94,5:95,6:95,7:123,8:94,9:212,10:6,11:7,12:3,13:25,14:150,15:144,16:149,17:197,18:700}
roster={c['id']:c for c in game['roster']};casters={}
for id,m in data['moves'].items():
    choice={'recover':65,'protect':7,'quickattack':25}.get(id,preferred[m['type']])
    if id!='aerialace' and id not in roster[choice]['learnset']:choice=next(c['id'] for c in game['roster'] if id in c['learnset'])
    casters[id]=choice
scene={'environment':game['environment'],'casters':casters,'target':68,'characters':{}}
def embedded(src):return 'data:image/png;base64,'+base64.b64encode((ROOT/src).read_bytes()).decode()
scene['ground']=embedded(game['environment']['groundSrc']);scene['objects']=embedded(game['environment']['objectsSrc'])
for n in set(casters.values())|{68}:
    arts={k:dict(v) for k,v in game['art'][str(n)].items() if k in ('idle','walk','shoot','melee','hurt','dash')}
    for artdata in arts.values():artdata['src']=embedded(artdata['src'])
    scene['characters'][str(n)]={'meta':roster[n],'art':arts}
parts.append('window.SCENE_DATA='+json.dumps(scene,ensure_ascii=False)+';\n'+(ROOT/'招式特效/真实场景.js').read_text())
html=(ROOT/'招式特效展台模板.html').read_text().replace('__DATA__',json.dumps(data,ensure_ascii=False)).replace('__EFFECTS__','\n'.join(parts)).replace('__ART__',json.dumps(art)).replace('__SPRITE__',sprite)
for token in ['__DATA__','__EFFECTS__','__ART__','__SPRITE__']:assert token not in html
out=ROOT/'招式特效-57招.html';out.write_text(html)
(outdir/'确认名单.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
(outdir/'构建记录.json').write_text(json.dumps({'count':len(ids),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'lanes':receipts,'source':'代码绘制首轮，非GPT生图，未修改正式游戏数值','browserVerified':False},ensure_ascii=False,indent=2))
print(out)
