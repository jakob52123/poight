"""Opt-in speed seam for legacy manual combat acceptance, not production behavior.

In ?test=1 the real step API already updates AND draws. The RAF loop only repeats
idle rendering (including huge raster maps); disabling that duplicate does not
replace step, draw, damage or any assertion. Normal/observe URLs remain untouched.
"""
import os
import sys
from functools import wraps
from pathlib import Path

MANUAL_RASTER_SUITES = {
    '验收-主角八招.py', '验收-跳跃.py', '验收-招式第1批.py', '验收-招式第2批.py',
    '验收-招式第3批.py', '验收-咬类招式.py', '验收-招式动画核心.py',
}

if (os.environ.get('POIGHT_VB2_MANUAL_HARNESS') == '1' and
        Path(sys.argv[0]).name in MANUAL_RASTER_SUITES):
    from playwright.sync_api import Browser

    _new_page = Browser.new_page

    @wraps(_new_page)
    def _manual_page(self, *args, **kwargs):
        page = _new_page(self, *args, **kwargs)
        page.add_init_script('''
          const manualParams = new URLSearchParams(location.search);
          if (manualParams.get('test') === '1' && manualParams.get('baseline') !== 'M4')
            window.requestAnimationFrame = () => 0;
        ''')
        return page

    Browser.new_page = _manual_page
