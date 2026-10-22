"""LOCAL TEST ONLY: overlay source on an excluded live build; no asset redistribution.
Download index to local-live.html and its assets separately. Not a replacement build.
"""
import ast
import json
import re
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build():
    source = (ROOT / 'local-live.html').read_text()
    tree = ast.parse((ROOT / '构建完整版.py').read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'compact_gba_css')
    ns = {'re': re}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<css>', 'exec'), ns)
    sheets = ['界面.css', '街机界面.css', '配招界面.css', '场景界面.css', '选人界面.css',
              '战斗界面方案.css', '手机操作.css', '演示模式.css', '界面-GBA.css', 'UI3/招式栏.css', '选人页.css']
    def text(f):
        return subprocess.check_output(['git', 'show', f'HEAD:{f}'], cwd=ROOT).decode() if '--before' in sys.argv else (ROOT/f).read_text()
    css = '\n'.join(ns['compact_gba_css'](text(f)) if f in ('界面-GBA.css', '选人页.css') else text(f) for f in sheets)
    source = re.sub(r'<style>.*?</style>', lambda _: '<style>' + css + '</style>', source, count=1, flags=re.S)
    template = (ROOT/'页面.html').read_text()
    a = template.index('<dialog id="setup"'); b = template.index('</dialog>', a)+9
    x = source.index('<dialog id="setup"'); y = source.index('</dialog>', x)+9
    source = source[:x] + template[a:b] + source[y:]
    x = source.index('window.PoightMobile = class'); y = source.index('\n};', x)+3
    source = source[:x] + (ROOT/'手机操作.js').read_text() + source[y:]
    start = source.index('const DATA = ') + len('const DATA = ')
    data, _ = json.JSONDecoder().raw_decode(source[start:])
    game_start = source.rfind('"use strict";', 0, start)
    game_end = source.index('</script>', start)
    game = (ROOT / '对战.js').read_text().replace('__GAME_DATA__', json.dumps(data, ensure_ascii=False))
    source = source[:game_start] + game + '\n' + source[game_end:]
    if (ROOT / '手机手柄.js').exists():
        source = source.replace('</head>', '<script>' + (ROOT / 'vendor/qrcode.js').read_text() +
                                '\n' + (ROOT / '手机手柄.js').read_text() + '</script></head>')
    (ROOT / 'index.html').write_text(source)

if __name__ == '__main__':
    build()
