"""Real candidate screenshots plus exhaustive portrait/icon audit (headless wrapper only)."""
import hashlib
import io
import json
import math
import os
import time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/M10/截图/第二段'
OUT.mkdir(parents=True,exist_ok=True)
RECORD=ROOT/'验收记录/M10/第二段'
html=(ROOT/'候选试玩.html').read_text()
data,_=json.JSONDecoder().raw_decode(html.split('const DATA = ',1)[1])
sha=hashlib.sha256(html.encode()).hexdigest()
errors=[];portraits=[];checks=[]
def check(name,ok,detail=None):
 checks.append(dict(name=name,ok=bool(ok),detail=detail))
 if not ok:print('FAIL',name,detail,flush=True)
def wait(p,fn,seconds=40):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if p.evaluate(fn):return
  p.wait_for_timeout(25)
 raise TimeoutError(fn)
# Reconstruct the shared sheet from the *large portrait atlas*, not icon.png.
sheet=Image.new('RGBA',(440,math.ceil(len(data['roster'])/10)*44))
for i,c in enumerate(data['roster']):
 a=data['portraits'][str(c['id'])]
 with Image.open(ROOT/'素材/立绘'/a['file']) as atlas:
  thumb=atlas.crop((0,0,a['width'],a['height'])).convert('RGBA')
 thumb=thumb.crop(thumb.getbbox());thumb.thumbnail((44,44),Image.Resampling.NEAREST)
 sheet.alpha_composite(thumb,(i%10*44+(44-thumb.width)//2,i//10*44+(44-thumb.height)//2))
buf=io.BytesIO();sheet.quantize(256,method=Image.Quantize.FASTOCTREE).save(buf,format='PNG',optimize=True)
check('200格共享图集逐字节来自大立绘',buf.getvalue()==(ROOT/data['gbaRoster']).read_bytes())
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True)
 for w,h in [(1440,900),(844,390),(667,375)]:
  ctx=browser.new_context(viewport={'width':w,'height':h},has_touch=w<1000,is_mobile=w<1000)
  p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
  response=p.goto(os.environ['POIGHT_TEST_URL'].rstrip('/')+'/?observe=1')
  check(f'{w}候选SHA',hashlib.sha256(response.body()).hexdigest()==sha)
  wait(p,'()=>document.querySelector("#setup").open && !document.querySelector("#startBattle").disabled && [...document.querySelectorAll("#playerPortrait,#enemyPortrait")].every(e=>e.dataset.frame)')
  p.screenshot(path=OUT/f'选人-初代151-{w}x{h}.png')
  if w==1440:
   for group in ['initial','popular']:
    p.locator(f'[data-group="{group}"]').click();p.wait_for_timeout(100)
    p.screenshot(path=OUT/f'选人-{"初代151" if group=="initial" else "人气精选49"}-{w}x{h}.png')
    rows=p.locator('.mon').evaluate_all('''els=>els.map(e=>{const i=e.querySelector('.mon-icon'),s=getComputedStyle(i);return {id:Number(e.dataset.id),image:s.backgroundImage,position:s.backgroundPosition,width:s.width,height:s.height,transform:s.transform};})''')
    for row in rows:
     n=data['iconOrder'].index(row['id'])
     row['largePortrait']=data['gbaRoster'] in row['image'] and row['position']==f'{-(n%10)*44}px {-int(n/10)*44}px' and row['width']=='44px' and row['height']=='44px' and row['transform']=='matrix(1.36, 0, 0, 1.36, 0, 0)'
     row['source']=data['portraits'][str(row['id'])]['src']
     portraits.append(row)
    tiles=[]
    for ident in [r['id'] for r in rows]:
     tiles.append(Image.open(io.BytesIO(p.locator(f'.mon[data-id="{ident}"]').screenshot())).convert('RGB'))
    tw,th=max(t.width for t in tiles),max(t.height for t in tiles)
    contact=Image.new('RGB',(tw*10,th*math.ceil(len(tiles)/10)), '#142c37')
    for n,t in enumerate(tiles):contact.paste(t,((n%10)*tw,(n//10)*th))
    contact.save(OUT/f'逐格大立绘-{group}-{len(tiles)}.png')
   mids=sorted({m for c in data['roster'] for m in c['defaultMoves']+c['learnset']})
   icons=p.evaluate('''moves=>moves.map(m=>{const key=m.kind==='guard'?'shield':['buff','heal','splash'].includes(m.kind)?'arrow':m.type;return {id:m.id,type:m.type,kind:m.kind,key,exists:Object.hasOwn(PoightUI3.pixels,key)&&Object.hasOwn(PoightUI3.pixels,m.type)};})''',[data['moves'][mid] for mid in mids])
   missing=[r for r in icons if not r['exists']]
   (RECORD/'招式图标覆盖.json').write_text(json.dumps(dict(moves=len(mids),types=sorted({r['type'] for r in icons}),categories=sorted({r['kind'] for r in icons}),missing=missing,missingCount=len(missing),records=icons),ensure_ascii=False,indent=2)+'\n')
   check('200只默认配招和可选池图标缺失0',not missing)
   # Random CPU must still sample the entire 200 roster, not the current tab.
   p.locator('[data-group="initial"]').click()
   p.evaluate('()=>{window.savedRandom=Math.random;Math.random=()=>.999999999;}')
   p.locator('#randomEnemy').click()
   check('CPU随机上界第200只887',p.locator('#enemyPortrait').get_attribute('data-id')=='887')
   p.evaluate('()=>{Math.random=window.savedRandom;}')
  if w==667:
   ctx.close();continue
  # Test mode only freezes battle time/sets the win; same candidate and UI.
  p.goto(os.environ['POIGHT_TEST_URL'].rstrip('/')+'/?test=1&lazy=1')
  wait(p,'()=>__waterTest.snapshot().artReady')
  p.locator('#battleMenuButton').click();p.locator('#setupButton').click()
  p.locator('[data-group="popular"]').click()
  p.locator('#choosePlayer').click();p.locator('.mon[data-id="445"]').click()
  p.locator('#chooseEnemy').click();p.locator('.mon[data-id="249"]').click()
  wait(p,'()=>[...document.querySelectorAll("#playerPortrait,#enemyPortrait")].every(e=>e.dataset.frame)')
  p.locator('#startBattle').click()
  wait(p,'()=>__waterTest.snapshot().phase==="versus"')
  p.wait_for_timeout(750)  # Capture after fighter entry, before the 1600ms VS timeout.
  p.screenshot(path=OUT/f'VS-{w}x{h}.png')
  wait(p,'()=>__waterTest.snapshot().phase==="playing"')
  p.evaluate('()=>{const t=__waterTest;t.arrange({ai:false,player:{x:1300,y:900,a:0},enemy:{x:1430,y:900,a:Math.PI},clearProjectiles:true});t.step(1);t.render();}')
  p.screenshot(path=OUT/f'对战-烈咬陆鲨-vs-洛奇亚-{w}x{h}.png')
  check(f'{w}真实对战445vs249',p.evaluate('()=>{const s=__waterTest.snapshot();return s.player.id===445 && s.enemy.id===249;}'))
  p.evaluate('()=>{__waterTest.arrange({enemy:{hp:0}});__waterTest.step(.02);__waterTest.render();}')
  wait(p,'()=>!document.querySelector("#matchOverlay").hidden && document.querySelector("#matchTitle").textContent==="胜利"')
  check(f'{w}结算胜利弹层可见',p.locator('#matchOverlay').is_visible())
  p.screenshot(path=OUT/f'结算-{w}x{h}.png')
  ctx.close()
 browser.close()
missing=[r for r in portraits if not r['largePortrait']]
check('200/200大立绘无小icon退回',len(portraits)==200 and not missing)
check('无JS错误',not errors,errors)
report=dict(candidateSHA256=sha,passed=sum(c['ok'] for c in checks),failed=sum(not c['ok'] for c in checks),jsErrors=len(errors),errors=errors,checks=checks,portraitCount=len(portraits),missingPortraits=missing,portraits=portraits,pngFallback724=data['portraits']['724'])
(RECORD/'截图审计.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['portraits','checks']},ensure_ascii=False))
raise SystemExit(bool(report['failed'] or errors))
