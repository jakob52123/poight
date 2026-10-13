import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    data = []
    for w, h in [(1440, 900), (844, 390), (390, 844), (667, 375)]:
        page = browser.new_page(viewport={'width': w, 'height': h}, has_touch=w < 1000,
                                is_mobile=w < 1000)
        page.goto(os.environ['POIGHT_TEST_URL'] + '?observe=1')
        page.wait_for_timeout(300)
        data.append(page.evaluate('''()=>({w:innerWidth,h:innerHeight,items:
          ['#setup','.setup-head','.setup-body','.dex','#roster','#pickPlayerPanel',
           '#pickEnemyPanel','.setup-foot','.setup-actions','#startBattle','.setup-credit',
           '#setupTitle','#typeFilterToggle','#choosePlayer','#chooseEnemy'].map(s=>{
           const e=document.querySelector(s),c=getComputedStyle(e);return {s,rect:e.getBoundingClientRect().toJSON(),
           css:Object.fromEntries(['display','position','gridArea','gridTemplateRows','gridTemplateColumns',
           'height','width','minHeight','minWidth','maxHeight','overflow','flex','flexWrap','transform',
           'fontSize','color','backgroundColor'].map(k=>[k,c[k]]))}})})'''))
        page.close()
    browser.close()
Path('验收记录/UI2/几何.json').write_text(json.dumps(data, indent=2, ensure_ascii=False))
print(json.dumps(data, ensure_ascii=False))
