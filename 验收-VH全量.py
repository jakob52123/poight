"""V1-core's complete 23-suite list, including the strengthened hero acceptance; serial only."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/集成批次/VH-final'
NAMES = ['体型移速', '体型招式回归', '生图实战', '绿宝石', '草丛', '竞技场', '主角八招',
         '选人页', '水溅跃', '头顶血条', '草丛藏身', '平衡钩子', '打击感瞄准', '大地图通行',
         '集成联动', '出招反馈', '界面方案', '跳跃', '招式第1批', '招式第2批', '招式第3批',
         '咬类招式', '招式动画核心']


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'POIGHT_TEST_URL': os.environ.get('POIGHT_TEST_URL', 'http://localhost:8877/')}
    summary = []
    for name in NAMES:
        print('RUN '+name, flush=True)
        result = subprocess.run([sys.executable, f'验收-{name}.py'], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=1800, check=False)
        (OUT / f'{name}.log').write_text(result.stdout+result.stderr)
        obj = None
        for pos, char in enumerate(result.stdout):
            if char == '{':
                try:
                    candidate, _ = json.JSONDecoder().raw_decode(result.stdout[pos:])
                    if isinstance(candidate, dict) and 'passed' in candidate:
                        obj = candidate
                        break
                except ValueError:
                    pass
        if obj is None:
            print(result.stdout[-3000:], result.stderr[-3000:], flush=True)
            return result.returncode or 1
        row = {'test': name, 'exitCode': result.returncode, 'passed': obj['passed'],
               'failed': obj.get('failed', sum(not c['ok'] for c in obj.get('checks', []))),
               'jsErrors': obj.get('jsErrors', len(obj.get('errors', [])))}
        summary.append(row)
        (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
        print(name+' '+json.dumps(row, ensure_ascii=False), flush=True)
        if row['exitCode'] or row['failed'] or row['jsErrors']:
            print(result.stderr[-3000:], flush=True)
            return 1
    total = {'suites': len(summary), 'passed': sum(s['passed'] for s in summary),
             'failed': sum(s['failed'] for s in summary), 'jsErrors': sum(s['jsErrors'] for s in summary)}
    (OUT / 'total.json').write_text(json.dumps(total, ensure_ascii=False, indent=2)+'\n')
    print('TOTAL '+json.dumps(total, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
