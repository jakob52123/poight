"""Incremental UI screenshots; run only via tools/远程执行.sh."""
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path('验收记录/UI2/截图')
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for w, h in [(1440, 900), (844, 390), (390, 844), (667, 375)]:
        context = browser.new_context(viewport={'width': w, 'height': h},
                                      has_touch=w < 1000, is_mobile=w < 1000)
        page = context.new_page()
        page.on('pageerror', lambda e: print('JSERROR', e))
        page.goto(os.environ['POIGHT_TEST_URL'] + '?test=1')
        for _ in range(600):
            if page.evaluate('window.__waterTest?.snapshot().artReady'):
                break
            time.sleep(.025)
        page.evaluate('''async()=>{const t=__waterTest,c=t.catalog(),s=t.snapshot();
          await t.select({...s.profile, player:25,enemy:6,map:'arena-formal',
            playerMoves:c.roster.find(c=>c.id===25).defaultMoves,
            enemyMoves:c.roster.find(c=>c.id===6).defaultMoves});
          t.reset(true);t.arrange({ai:false});t.step(.01)}''')
        page.screenshot(path=OUT / f'对战-{w}x{h}.png')
        print(w, h, page.evaluate('''()=>({scroll:document.documentElement.scrollWidth,
          map:__waterTest.snapshot().arenaView.minimap,
          buttons:[...document.querySelectorAll('.skill,#jumpButton,#dashButton')].map(e=>
          ({id:e.id,box:e.getBoundingClientRect().toJSON()}))})'''))
        page.locator('#battleMenuButton').click()
        page.locator('#setupButton').click()
        time.sleep(.4)
        page.screenshot(path=OUT / f'选人-{w}x{h}.png')
        context.close()
    browser.close()
