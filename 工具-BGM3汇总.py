"""Audit complete M6a counts, retention of all 142 music checks, and audio measurements."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/集成批次/BGM3-final'


def load(path):
    return json.loads(path.read_text())


def main():
    summary = load(OUT / 'summary.json')
    previous = load(ROOT / '验收记录/集成批次/BGM2-final/summary.json')
    assert len(summary) == len(previous) == 26
    assert all(s['exitCode'] == s['failed'] == s['jsErrors'] == 0 for s in summary)
    old = {s['test']: s['passed'] for s in previous if s['test'] != '战斗音乐'}
    new = {s['test']: s['passed'] for s in summary if s['test'] != '战斗音乐'}
    assert old == new and sum(new.values()) == 67876
    old_checks = load(ROOT / '验收记录/集成批次/BGM2-final/战斗音乐.json')['checks']
    new_checks = load(OUT / '战斗音乐.json')['checks']
    assert len(old_checks) == 142
    renames = {'默认红血方案R2': '默认红血方案R3'}
    assert {renames.get(c['name'], c['name']) for c in old_checks} <= {
        c['name'] for c in new_checks}
    assert all(c['ok'] for c in new_checks)
    performance = load(ROOT / '验收记录/丰缘全图/性能对比.json')
    candidate_sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
    assert candidate_sha == performance['runs'][1]['candidateSHA256']
    audio = load(ROOT / '验收记录/战斗音乐/BGM3试听/音色核验.json')
    for metrics in audio['tracks'].values():
        for segment in ['audition10s', 'full60s']:
            assert metrics[segment]['centroidReduction'] >= .25
            assert metrics[segment]['above4kReduction'] >= .4
        assert abs(metrics['lufsDifference']) <= 1
        assert metrics['runtimePeakDBFS'] <= -1 and not metrics['clippedSamples']
        assert metrics['seamPeakDifferenceDB'] < 3
    assert not audio['jsErrors'] and not audio['dynamic']['alarmEvents']
    assert (ROOT / '战斗音乐.js').stat().st_size < 25000
    total = {'suites': len(summary), 'passed': sum(s['passed'] for s in summary),
             'failed': sum(s['failed'] for s in summary),
             'jsErrors': sum(s['jsErrors'] for s in summary)}
    receipt = {'candidateSHA256': candidate_sha, 'retainedMusicChecks': 142,
               'renamedAssertions': renames, 'legacyAlarmStrategy': 'explicit r2',
               'oldSuiteCountsUnchanged': True,
               'musicModuleBytes': (ROOT / '战斗音乐.js').stat().st_size,
               'total': total, 'audio': audio}
    (OUT / '保留断言核验.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print('战斗音乐 ' + json.dumps(next(s for s in summary if s['test'] == '战斗音乐')))
    print('TOTAL ' + json.dumps(total))


if __name__ == '__main__':
    main()
