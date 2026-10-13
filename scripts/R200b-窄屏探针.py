"""Diagnose real pointer controls, with optional test-only grid sizing experiment."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/R200/补充1'
OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    page=browser.new_page(viewport=dict(width=390,height=844))
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/')+'/?observe=1')
    for _ in range(600):
        if page.evaluate('()=>document.querySelector("#setup").open && !document.querySelector("#startBattle").disabled'):break
        page.wait_for_timeout(50)
    page.locator('.mon[data-id="25"]').click()
    page.locator('#toggleLoadout').click()
    page.locator('#moveChoice0').click()
    page.locator('#moveCatalog button:enabled[aria-pressed="false"]').first.click()
    def geometry():
        return page.evaluate('''()=>Object.fromEntries(['#loadoutPanel','#moveCatalog','.loadout-title','#defaultMoves','#closeMoves','#moveSlots'].map(sel=>{
          const e=document.querySelector(sel),r=e.getBoundingClientRect(),s=getComputedStyle(e),at=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
          return [sel,{rect:r.toJSON(),height:s.height,minHeight:s.minHeight,overflow:s.overflow,gridRows:s.gridTemplateRows,gridAutoRows:s.gridAutoRows,
            scrollHeight:e.scrollHeight,scrollTop:e.scrollTop,interceptor:at?.outerHTML.slice(0,500)}];}));''')
    records=[]
    for label,experiment in [('before',False),('max-content-experiment',True)]:
        if experiment:page.locator('#loadoutPanel').evaluate("e=>e.style.gridAutoRows='max-content'")
        record=dict(label=label,before=geometry())
        try:
            page.locator('#defaultMoves').click(timeout=2000)
            record['click']=True
        except Exception as exc:
            record.update(click=False,error=str(exc))
        record['after']=geometry()
        page.screenshot(path=str(OUT/f'窄屏-{label}.png'))
        records.append(record)
    (OUT/'窄屏探针.json').write_text(json.dumps(dict(records=records,errors=errors),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(clicks=[r['click'] for r in records],errors=errors),ensure_ascii=False))
    browser.close()
