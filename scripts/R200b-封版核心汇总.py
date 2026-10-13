"""Final-SHA core receipt, independent of whether the long 49-suite rerun finished."""
import hashlib
import json
import re
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/R200/补充1'
SEALED=OUT/'minimal-sealed-8992/R200b'
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
candidate=sha(ROOT/'候选试玩.html')
assert sha(SEALED/'候选试玩.html')==candidate
exit_rows=load(SEALED/'验收记录/R200/补充1/核心退出.json')
assert len(exit_rows)==12 and all(r['exitCode']==0 for r in exit_rows)
for name in ['冒烟.json','逐精灵验收-R200b.json','选人验收.json','离线.json','选人-1440x900.png','选人-844x390.png','选人-667x375.png']:
    shutil.copy2(SEALED/'验收记录/R200'/name,OUT/name)
shutil.copy2(SEALED/'验收记录/体型与移速/浏览器验收.json',OUT/'体型移速详情.json')
shutil.copy2(SEALED/'验收记录/首开加载/R200b-final/network.json',OUT/'首开-network.json')
batch=SEALED/'验收记录/集成批次/R200b-sealed-ui'
assert (batch/'candidate-sha256.txt').read_text().strip()==candidate
suite_rows=load(batch/'summary.json')
assert len(suite_rows)==6 and all(not r['failed'] and not r['exitCode'] and not r['jsErrors'] for r in suite_rows)
shutil.copytree(batch,OUT/'回归证据/R200b-sealed-ui',dirs_exist_ok=True)
body=load(OUT/'体型移速详情.json')
assert body['candidateSHA256']==candidate and all(c['ok'] for c in body['checks']) and not body['errors']
assert body['passed']==1848 and any(c['name']=='No JS errors or external runtime requests' for c in body['checks'])
extras={}
for name in ['冒烟.json','逐精灵验收-R200b.json','选人验收.json','离线.json']:
    r=load(OUT/name)
    assert r.get('candidateSHA256',r.get('testedHTMLSHA256'))==candidate
    assert not r.get('failed') and not r.get('jsErrors') and not r.get('castFailures')
    extras[name]={k:v for k,v in r.items() if k not in ('rows','records','casts')}
network=load(OUT/'首开-network.json')
assert network['selection']['bytes']<=1000000 and network['selection']['seconds']<=3.5 and not network['errors']
urls=[r['url'] for r in network['requests'] if r['phase']=='battle']
characters={int(m[1]) for url in urls if (m:=re.search(r'/assets/(\d{4})-',url))}
metadata={int(m[1]) for url in urls if (m:=re.search(r'/character-meta-(\d{4})-',url))}
assert characters==metadata=={6,25}
old50=load(ROOT/'验收记录/R200/数据核验.json')
release=load(ROOT/'验收记录/R200/发布核验.json')
assert not old50['changed'] and release['candidateSHA256']==candidate and not release['original50ArtAndLandmarksChanged']
report=dict(candidateSHA256=candidate,suites=suite_rows,extra=extras,bodyPassed=body['passed'],
            coldBefore=load(ROOT/'验收记录/首开加载/R200-before/network.json')['selection'],
            coldAfter=network['selection'],battleAfter=network['battle'],
            battleCharacterIDs=sorted(characters),battleMetadataIDs=sorted(metadata),
            old50=old50,release=release,
            full49Status='Separate long-running regression; this receipt certifies only the final-SHA core and six affected UI suites, not a completed 49-suite rerun.')
(OUT/'核心总验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('extra','release','old50')},ensure_ascii=False))
