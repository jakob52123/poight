"""Run the unchanged DEP --check locally, with all writes confined to R200.
Read DEP first: --check returns before root_baseline/upload/ssh, finally writes
its receipt alongside the script. Copy the three unchanged modules here so even
that receipt cannot modify DEP. Never execute a deployment mode.
"""
import csv
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/R200'
# Explicit fallback when another task updates live DEP: only the already-audited,
# hash-pinned local snapshot may run. Never silently accept new deployment code.
DEP=(OUT/'发布器') if '--archived-dep' in sys.argv else ROOT.parent/'DEP/部署-子域'
CHECK=OUT/'发布器'
FROZEN=OUT/'候选包'
CHECK.mkdir(parents=True,exist_ok=True)
FROZEN.mkdir(parents=True,exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
# Fail closed if a future DEP revision changes the audited check-only path.
reviewed = {
    '发布子域.py': 'd07400983f71594cffc98e4234564d759d5c7c106128c5f2cf063233b2b363cb',
    'release_lib.py': '65ec43fcb90f46c369e7e2d1001ca62bf1f7518cd02e923e4b1e23ef225284b9',
    '公网工具.py': '1673f8ae936cfb2f67628bd54ced9b5622c0c7b5ade6e4e92dc8b6a7f46f39f1',
}
modules={}
for name, expected in reviewed.items():
    assert sha((DEP/name).read_bytes()) == expected, 'DEP changed; review before executing --check'
    if (DEP/name).resolve() != (CHECK/name).resolve():
        shutil.copy2(DEP/name,CHECK/name)
    modules[name]=sha((CHECK/name).read_bytes())
manifest=json.loads((ROOT/'候选发布清单.json').read_text())
shutil.copy2(ROOT/'候选试玩.html',FROZEN/'index.html')
shutil.copy2(ROOT/'候选发布清单.json',FROZEN/'发布清单.json')
(FROZEN/'index.html.gz').write_bytes(gzip.compress((FROZEN/'index.html').read_bytes(),mtime=0))
for name,item in manifest['assets'].items():
    p=ROOT/name
    assert sha(p.read_bytes())==item['sha256'] and p.stat().st_size==item['bytes']
    dest=FROZEN/name;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,dest)
command=[sys.executable,str(CHECK/'发布子域.py'),str(FROZEN),'--check']
p=subprocess.run(command,capture_output=True,text=True,check=True)
(OUT/'发布器-check.log').write_text(p.stdout+p.stderr)
sys.path.insert(0,str(CHECK))
from release_lib import read_directory,assets_map,MAX_COUNT,MAX_FILE,MAX_TOTAL
m,data=read_directory(FROZEN)
whitelist=assets_map(m)
(OUT/'本地资产白名单.conf').write_text(whitelist)
assert len(whitelist.splitlines())==len(data)+3
# Compare complete six-role metadata and landmarks, not only the body TSV.
text=(ROOT/'候选试玩.html').read_text()
d=json.JSONDecoder().raw_decode(text[re.search(r'const DATA\s*=\s*',text).end():])[0]
old=json.loads((OUT/'原50基线.json').read_text())
changes=[]
for c in old['roster']:
    n=c['id'];ref=d['characterPacks'][str(n)]
    offline=(ROOT/ref['offline']).read_text()
    payload=json.loads(offline.split('=',1)[1].removesuffix(';\n'))
    if payload['art']!=old['art'][str(n)]:changes.append([n,'art'])
    if payload['moveAnchors']!=c.get('moveAnchors',{}):changes.append([n,'moveAnchors'])
assert not changes,changes
stone=d['generatedFx']['stoneedge']['sha256']
assert stone=='ec3849ad57d94f0a64a8b95e2f9e188051659d7eb0f5ccc2b836f6684c66ed39'
assert sha((ROOT / d['generatedFx']['stoneedge']['src']).read_bytes()) == stone
names={int(r['pokemon_species_id']):r['name'] for r in csv.DictReader((ROOT/'素材/角色库/原始/pokemon_species_names.csv').open()) if r['local_language_id']=='12'}
name_diffs=[dict(id=c['id'],library=c['name'],zhHans=names[c['id']]) for c in d['roster'] if c['name']!=names[c['id']]]
report=dict(candidateSHA256=sha((ROOT/'候选试玩.html').read_bytes()),manifestSHA256=sha((ROOT/'候选发布清单.json').read_bytes()),
            assets=len(manifest['assets']),releaseFiles=len(data),bytes=sum(map(len,data.values())),
            whitelistBytes=len(whitelist.encode()),maxPathBytes=max(len(n.encode()) for n in data),
            limits=dict(files=MAX_COUNT,fileBytes=MAX_FILE,totalBytes=MAX_TOTAL,pathBytes=220),
            checkResult='validated-only',serverCommands=0,
            checkSource='hash-pinned archived DEP snapshot' if '--archived-dep' in sys.argv else 'live DEP audited hash',
            original50ArtAndLandmarksChanged=changes,
            stoneEdgeSHA256=stone,rosterOrder=[c['id'] for c in d['roster']],
            simplifiedNameDifferences=name_diffs,nameReference='archived PokéAPI species_names local_language_id=12 (community reference, not independent official-site audit)',
            noteworthyNames={'373':'暴飞龙','778':'谜拟丘'},checkModulesSHA256=modules,command=command)
(OUT/'发布核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['rosterOrder','command']},ensure_ascii=False))
