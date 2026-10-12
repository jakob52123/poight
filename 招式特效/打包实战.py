"""Reuse hashed raster atlases, with explicit (unapproved for balance) playtest timing overrides."""
from pathlib import Path
from PIL import Image
import json,hashlib
from 招式特效.主角打包 import prepare, finish
from 招式特效.第1批打包 import prepare as prepare_r1, finish as finish_r1
from 招式特效.第3批参数 import prepare as prepare_r3, finish as finish_r3
from 招式特效.咬类打包 import prepare as prepare_fangs, finish as finish_fangs
ROOT=Path(__file__).resolve().parents[1]
def build(move_ids,output):
 record=json.loads((ROOT/'招式特效/生图重做/实景预览/构建记录.json').read_text())
 specs=json.loads((ROOT/'招式特效/实战绘制.json').read_text())['moves'];out={}
 prepare(ROOT, record, specs)
 prepare_r1(ROOT, record, specs)
 prepare_r3(ROOT, record, specs)
 prepare_fangs(ROOT, record, specs)
 for mid in sorted(set(move_ids)&specs.keys()):
  rec=record['assets'][mid];d=dict(specs[mid]);p=(ROOT/rec['output']).resolve();assert p.is_relative_to(ROOT.resolve());raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==rec['outputSHA256']
  with Image.open(p) as im:assert im.mode=='RGBA' and im.size==(d['fw']*d.get('columns',1),d['fh']*4)
  d['src']=output('move-fx-'+sha[:16]+'.png',raw);d['sha256']=sha;d['frames']=4;d['humanApproved']=mid in ('flamethrower','watergun','stoneedge')
  r={'range':d['reach'],'windup':.42,'recovery':.25,'speed':180}
  # The old library sometimes used target zones for traveling art (notably Fire Blast).
  # Route by the explicit generated-action contract, not by the old renderer label.
  if d['mode'] in ('shot','stream','wave'):r.update(kind='beam' if d['mode']=='stream' else 'shot',radius=min(26,max(4,d['height']*.22)))
  if d['mode']=='rush':r.update(kind='rush')
  if d['mode']=='selfarea':r.update(kind='nova')
  if d['mode'] in ('ground','fall'):r.update(kind='zone')
  if d['mode']=='melee':r.update(kind='melee')
  if d['mode']=='melee':r.update(range=min(65,max(50,d['reach'])),windup=.24,recovery=.28)
  if d['mode']=='support':r.update(windup=.32)
  if d['mode']=='rush':r.update(rushSpeed=290,windup=.3)
  if mid=='fireblast':r.update(speed=145,radius=23,windup=.5)
  if mid=='flamethrower':r.update(speed=165,radius=13);d.update(height=25)
  if mid=='watergun':r.update(speed=190,radius=3,windup=.24);d.update(height=8)
  if mid in ('solarbeam','hyperbeam'):r.update(speed=560,windup=.85)
  if mid=='icebeam':r.update(speed=250,radius=4);d.update(height=9)
  if mid=='thunderbolt':d.update(height=16)
  if mid=='wildcharge':r.update(rushSpeed=470)
  if mid=='bravebird':r.update(rushSpeed=560)
  if mid=='surf':r.update(kind='rush',rushSpeed=180,range=165,windup=.42);d.update(mode='ride')
  if mid=='agility':r.update(range=150,windup=.16,recovery=.16)
  if mid=='earthquake':r.update(range=72);d.update(width=144,height=115)
  finish(mid, d, r)
  finish_r1(mid, d, r)
  finish_r3(mid, d, r)
  finish_fangs(ROOT, mid, d, r, output)
  d['runtime']=r;out[mid]=d
 receipt={'status':'candidate_runtime_integration_visual_timing_review_pending','count':len(out),'ids':list(out),'excluded':sorted(specs.keys()-set(move_ids)),'stoneedgeSHA256':out['stoneedge']['sha256'],'newGeneration':any(d.get('batch2') for d in out.values()),'damageHPAttackDefenseChanged':False,'timingAndRangeOverrides':{k:v['runtime'] for k,v in out.items()},'limitations':['R2已换单枚回旋叶刃；暴风雪不属本批，仍待重画。','非首批角色/方向的嘴翼拳尾锚点仍待逐项人工校准。','接入与程序检查不等于57项美术/手感返修全部通过。','本轮不采用数值Agent的HP/攻防公式。']}
 (ROOT/'招式特效/实战打包记录.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');return out
