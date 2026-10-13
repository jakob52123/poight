"""Coordinate-only diagnostic of unchanged native touch gesture; no game CSS changes."""
import importlib.util
import inspect
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/M10/第二段/iPad滑动诊断'
OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('mob',ROOT/'验收-手机适配.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source=inspect.getsource(m.touches)
source=source.replace("            xx=bb['x']+bb['width']/2", """            xx=bb['x']+bb['width']/2
            print('HIT', selector, p.evaluate('''([x,y])=>{let e=document.elementFromPoint(x,y);return {x,y,target:e?.outerHTML.slice(0,300),chain:(()=>{let r=[];for(let a=e;a;a=a.parentElement)r.push({tag:a.tagName,id:a.id,cls:a.className,touch:getComputedStyle(a).touchAction,box:a.getBoundingClientRect().toJSON()});return r;})()};}''',[xx,bottom]),flush=True)""")
with sync_playwright() as pw:
 for inset in [5,15,25]:
  m.SHOTS=OUT/str(inset);m.SHOTS.mkdir(exist_ok=True)
  modified=source.replace("d['viewport']['height'])-5",f"d['viewport']['height'])-{inset}")
  exec(compile(modified,'native-touch-diagnostic','exec'),m.__dict__)
  r=m.touches(pw,'iPad Mini')
  (OUT/f'inset-{inset}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
  print('INSET',inset,json.dumps(r['scrollGesture']['roster']),flush=True)
