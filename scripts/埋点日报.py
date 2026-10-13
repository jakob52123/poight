"""First-party telemetry report, stdlib only. All calendar metrics use Asia/Shanghai."""
import argparse
import base64
import json
import re
from collections import Counter, defaultdict
from datetime import date as calendar_date
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Shanghai')
EVENTS = {'page_view', 'select_ready', 'pick', 'loadout_change', 'battle_start_click',
          'battle_ready', 'first_input', 'battle_end', 'rematch', 'change_pokemon',
          'quit', 'setting', 'link_click', 'perf_low', 'error', 'session_end'}
FUNNEL = ['page_view', 'select_ready', 'battle_start_click', 'battle_ready',
          'first_input', 'battle_end', 'rematch']
FIELDS = {
    'page_view': 'ref src utm dt w h o lang sa rv days', 'select_ready': 'ms kb',
    'pick': 's n', 'loadout_change': 'k v', 'battle_start_click': 'a c m l x y z',
    'battle_ready': 'ms kb', 'first_input': 'ms i',
    'battle_end': 'r sec h hit hurt ev u f pa', 'rematch': 'ms', 'change_pokemon': 'ms',
    'quit': 'sec a c', 'setting': 'k v', 'link_click': 'to', 'perf_low': 'f dt',
    'error': 'm f l', 'session_end': 'ms n',
}


def parse_line(line):
    if line.lstrip().startswith('{'):
        row = json.loads(line)
        stamp, args = row['ts'], row['args']
    else:
        match = re.fullmatch(r'(\S+)\s+\S+\s+"(.*)"\s*', line.strip())
        if not match:
            raise ValueError('not JSONL or nginx event log')
        stamp, args = match.groups()  # Masked address is deliberately discarded.
        args = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m[1], 16)), args)
    fields = parse_qs(args, keep_blank_values=True, strict_parsing=True)
    if any(len(values) != 1 for values in fields.values()):
        raise ValueError('duplicate parameter')
    fields = {k: v[0] for k, v in fields.items()}
    if set(fields) != {'v', 'e', 'd', 's', 't', 'b', 'p'} or fields['v'] != '1':
        raise ValueError('protocol')
    if fields['e'] not in EVENTS or len(('/e?' + args).encode()) > 600:
        raise ValueError('event or size')
    stamp = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('timestamp requires timezone')
    payload = json.loads(base64.urlsafe_b64decode(fields['p'] + '=' * (-len(fields['p']) % 4)))
    tick = int(fields['t'])
    if tick < 0 or not isinstance(payload, dict):
        raise ValueError('payload')
    if not set(FIELDS[fields['e']].split()).issubset(payload):
        raise ValueError('missing event properties')
    return {**fields, 'p': payload, 't': tick, 'ts': stamp,
            'date': stamp.astimezone(TZ).date().isoformat(), 'raw': args}


def load(path):
    events, invalid, seen, duplicate = [], 0, set(), 0
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            row = parse_line(line)
            key = (row['s'], row['e'], row['t'], row['p'].__repr__())
            if key in seen:
                duplicate += 1
                continue
            seen.add(key)
            events.append(row)
        except (ValueError, KeyError, TypeError, UnicodeError):
            invalid += 1
    return events, invalid, duplicate


def fraction(n, d):
    return {'n': n, 'base': d, 'rate': round(n / d, 4) if d else None}


def distribution(values):
    values = sorted(values)
    def percentile(q):
        at = (len(values) - 1) * q
        lo = int(at)
        hi = min(lo + 1, len(values) - 1)
        return round(values[lo] + (values[hi] - values[lo]) * (at - lo), 1)
    return {'n': len(values), 'median': percentile(.5) if values else None,
            'p90': percentile(.9) if values else None}


def counter_table(counter):
    base = sum(counter.values())
    return {str(k): fraction(v, base) for k, v in sorted(counter.items(), key=lambda x: str(x[0]))}


def report(events, date, invalid=0, duplicate=0):
    day = [e for e in events if e['date'] == date]
    sessions = defaultdict(list)
    for e in events:
        sessions[e['s']].append(e)
    # Attribution persists through rematches; a fresh ready always starts a new battle.
    ends, quits, lows, ready_rows = [], [], [], []
    for rows in sessions.values():
        config, current = {}, None
        for e in sorted(rows, key=lambda e: (e['t'], e['ts'])):
            if e['e'] == 'battle_start_click':
                config = e['p']
            elif e['e'] == 'battle_ready':
                current = {'config': config, 'ready': e, 'low': False}
                if e['date'] == date:
                    ready_rows.append(current)
            elif e['e'] == 'perf_low':
                if current:
                    current['low'] = True
                if e['date'] == date:
                    lows.append(e)
            elif e['e'] in ('battle_end', 'quit'):
                if e['date'] == date:
                    item = {'event': e, 'config': current['config'] if current else config}
                    (ends if e['e'] == 'battle_end' else quits).append(item)
                current = None
    opened = [e for e in day if e['e'] == 'page_view']
    devices = {e['d'] for e in opened}
    active = {e['s'] for e in day}
    errors = [e for e in day if e['e'] == 'error']
    error_sessions = {e['s'] for e in errors}
    funnel_counts, durations = Counter(), defaultdict(list)
    for rows in sessions.values():
        ordered = sorted(rows, key=lambda e: (e['t'], e['ts']))
        # Cohort is the sessions opened on this date; allow conversion after midnight.
        if not any(e['e'] == 'page_view' and e['date'] == date for e in ordered):
            continue
        cursor, prev = 0, None
        for name in FUNNEL:
            found = None
            for i in range(cursor, len(ordered)):
                if ordered[i]['e'] == name:
                    found, cursor = ordered[i], i + 1
                    break
            if found is None:
                break
            funnel_counts[name] += 1
            if prev:
                durations[name].append(found['t'] - prev['t'])
            prev = found
    funnel = []
    for i, name in enumerate(FUNNEL):
        base = funnel_counts[FUNNEL[i - 1]] if i else len(opened)
        funnel.append({'event': name, **fraction(funnel_counts[name], base),
                       'from_open': fraction(funnel_counts[name], len(opened))['rate'],
                       'ms': distribution(durations[name])})
    visits, first = defaultdict(set), {}
    for e in sorted(events, key=lambda e: e['ts']):
        if e['e'] != 'page_view':
            continue
        visits[e['d']].add(e['date'])
        if e['p'].get('rv') is False:
            first.setdefault(e['d'], e['date'])
    retention = {}
    for n in (1, 7):
        cohort_date = (datetime.fromisoformat(date).date() - timedelta(days=n)).isoformat()
        cohort = {d for d, first_date in first.items() if first_date == cohort_date}
        retention[f'd{n}'] = {'cohort': cohort_date,
                               **fraction(sum(date in visits[d] for d in cohort), len(cohort))}
    picks = defaultdict(Counter)
    loadouts, settings, links = defaultdict(Counter), defaultdict(Counter), Counter()
    maps, tiers, results = Counter(), Counter(), Counter()
    pokemon, moves = defaultdict(Counter), defaultdict(Counter)
    for e in day:
        p = e['p']
        if e['e'] == 'pick':
            picks[p.get('s', 'unknown')][str(p.get('n'))] += 1
        elif e['e'] in ('loadout_change', 'setting'):
            dest = loadouts if e['e'] == 'loadout_change' else settings
            dest[p.get('k', 'unknown')][json.dumps(p.get('v'), ensure_ascii=False)] += 1
        elif e['e'] == 'link_click':
            links[p.get('to', 'unknown')] += 1
        elif e['e'] == 'battle_start_click':
            maps[p.get('m', 'unknown')] += 1
            tiers[p.get('l', 'unknown')] += 1
    for item in ends:
        p, config = item['event']['p'], item['config']
        result = p.get('r', 'unknown')
        results[result] += 1
        for side, key, wins in [('player', 'a', result == 'win'), ('enemy', 'c', result == 'lose')]:
            ident = str(config.get(key, 'unknown'))
            pokemon[side + ':' + ident]['games'] += 1
            pokemon[side + ':' + ident]['wins'] += int(wins)
        for i, (side, key) in enumerate([('player', 'x'), ('enemy', 'y')]):
            counts = p.get('u', [[], []])
            for j, mid in enumerate(config.get(key, [])):
                if i < len(counts) and j < len(counts[i]):
                    moves[side][mid] += counts[i][j]
    per_device = Counter(item['event']['d'] for item in ends)
    end_payloads = [item['event']['p'] for item in ends]
    exp = {
        'selection_ms': distribution([e['p']['ms'] for e in day if e['e'] == 'select_ready']),
        'selection_kb': distribution([e['p']['kb'] for e in day if e['e'] == 'select_ready']),
        'battle_load_ms': distribution([e['p']['ms'] for e in day if e['e'] == 'battle_ready']),
        'battle_extra_kb': distribution([e['p']['kb'] for e in day if e['e'] == 'battle_ready']),
        'first_input_ms': distribution([e['p']['ms'] for e in day if e['e'] == 'first_input']),
        'fps': distribution([p['f'] for p in end_payloads if p.get('f', 0) > 0]),
        'low_fps': fraction(sum(r['low'] for r in ready_rows), len(ready_rows)),
        'low_fps_events': len(lows), 'errors': len(errors),
        'error_rate': fraction(len(error_sessions), len(active)),
        'error_messages': dict(Counter(e['p'].get('m', '') for e in errors)),
        'devices': counter_table(Counter(e['p'].get('dt', 'unknown') for e in opened)),
        'orientation': counter_table(Counter(e['p'].get('o', 'unknown') for e in opened)),
        'screens': dict(Counter(f"{e['p'].get('w')}x{e['p'].get('h')}" for e in opened)),
        'language': dict(Counter(e['p'].get('lang', 'unknown') for e in opened)),
        'standalone': fraction(sum(bool(e['p'].get('sa')) for e in opened), len(opened)),
        'inputs': counter_table(Counter(e['p'].get('i', 'unknown') for e in day
                                       if e['e'] == 'first_input')),
        'paused': fraction(sum(bool(p.get('pa')) for p in end_payloads), len(ends)),
        'battle_seconds': distribution([p['sec'] for p in end_payloads]),
        'remaining_hp': distribution([p['h'] for p in end_payloads]),
        'hits': sum(p.get('hit', 0) for p in end_payloads),
        'taken': sum(p.get('hurt', 0) for p in end_payloads),
        'dodges': sum(p.get('ev', 0) for p in end_payloads),
        'quit': fraction(len(quits), len(ends) + len(quits)),
        'quit_seconds': distribution([item['event']['p']['sec'] for item in quits]),
        'quit_player_hp': distribution([item['event']['p']['a'] for item in quits]),
        'quit_enemy_hp': distribution([item['event']['p']['c'] for item in quits]),
        'rematch_ms': distribution([e['p']['ms'] for e in day if e['e'] == 'rematch']),
        'change_ms': distribution([e['p']['ms'] for e in day if e['e'] == 'change_pokemon']),
        'session_ms': distribution([e['p']['ms'] for e in day if e['e'] == 'session_end']),
    }
    def origin(ref):
        if ref == 'direct':
            return 'direct'
        if ref == 'github.com' or ref.endswith('.github.com'):
            return 'github.com'
        if ref == 'douyin.com' or ref.endswith('.douyin.com') or ref == 'douyin':
            return 'douyin'
        return 'other'
    return {
        'date': date, 'timezone': 'Asia/Shanghai', 'events': len(day),
        'invalid_lines': invalid, 'duplicate_lines': duplicate,
        'north_star': len(ends), 'devices': len(devices), 'sessions': len(active),
        'games_per_device': {'n': len(devices | set(per_device)), 'games': len(ends),
                             'mean': round(len(ends) / len(devices | set(per_device)), 2)
                             if devices | set(per_device) else None},
        'games_per_playing_device': distribution(list(per_device.values())),
        'funnel': funnel, 'retention': retention, 'experience': exp,
        'content': {'picks': {k: counter_table(v) for k, v in picks.items()},
                    'pokemon_win_rate': {k: fraction(v['wins'], v['games']) for k, v in pokemon.items()},
                    'moves': {k: dict(v) for k, v in moves.items()},
                    'maps': counter_table(maps), 'difficulty': counter_table(tiers),
                    'results': dict(results), 'settings': {k: dict(v) for k, v in settings.items()},
                    'loadouts': {k: dict(v) for k, v in loadouts.items()}, 'links': dict(links)},
        'sources': {'referrer': counter_table(Counter(origin(e['p'].get('ref', 'direct')) for e in opened)),
                    'domains': dict(Counter(e['p'].get('ref', 'direct') for e in opened)),
                    'from': counter_table(Counter(e['p'].get('src') or 'none' for e in opened)),
                    'utm_source': counter_table(Counter(e['p'].get('utm') or 'none' for e in opened))},
        'event_counts': dict(Counter(e['e'] for e in day)),
        'notes': ['n<30 为小样本，勿把波动当结论。',
                  '留存只使用日志内 rv=false 的首次访客；请输入完整历史，删除存储/换设备不可识别。',
                  '漏斗按当日打开的会话、顺序首达；日完成数按结算日，跨日漏斗不等于日完成数。',
                  '0 样本写 N/A；下载 KB 为 Resource Timing（缓存常为 0），不是精确计费流量。',
                  '节流/隐私拒绝/拦截器/关闭页面信标丢失会低估，匿名设备不等于人数。'],
    }


def markdown(data):
    def rate(r):
        value = 'N/A' if r['rate'] is None else f"{r['rate']:.1%}"
        return f"{value}（n={r['n']}/{r['base']}）"
    def dist(d):
        return f"中位数 {d['median'] if d['median'] is not None else 'N/A'} / P90 {d['p90'] if d['p90'] is not None else 'N/A'}（n={d['n']}）"
    lines = [f"# Poight 埋点日报 · {data['date']}（北京时间）", '',
             f"北极星：**完成 {data['north_star']} 局**；匿名设备 {data['devices']}，会话 {data['sessions']}，事件 {data['events']}。",
             f"单设备平均对局：{data['games_per_device']['mean'] if data['games_per_device']['mean'] is not None else 'N/A'}（n={data['games_per_device']['n']}）；对局设备分布：{dist(data['games_per_playing_device'])}。",
             f"解析：坏行 {data['invalid_lines']}，重复行 {data['duplicate_lines']}。", '',
             '## 漏斗（相邻转化；相邻耗时 ms）',
             '| 步骤 | 转化 | 自打开转化 | 耗时 |', '|---|---|---|---|']
    for f in data['funnel']:
        overall = 'N/A' if f['from_open'] is None else f"{f['from_open']:.1%}"
        lines.append(f"| {f['event']} | {rate(f)} | {overall} | {dist(f['ms'])} |")
    lines += ['', '## 留存']
    for key, value in data['retention'].items():
        lines.append(f"- {key}（{value['cohort']} 首访 cohort）：{rate(value)}")
    lines += ['', '## 体验']
    for key, value in data['experience'].items():
        if isinstance(value, dict) and 'median' in value:
            text = dist(value)
        elif isinstance(value, dict) and 'rate' in value:
            text = rate(value)
        else:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f'- {key}：{text}')
    lines += ['', '## 内容']
    for key, value in data['content'].items():
        lines.append(f'- {key}：{json.dumps(value, ensure_ascii=False, sort_keys=True)}')
    lines += ['', '## 来源']
    for key, value in data['sources'].items():
        lines.append(f'- {key}：{json.dumps(value, ensure_ascii=False, sort_keys=True)}')
    lines += ['', '## 口径与小样本提醒', *['- ' + n for n in data['notes']], '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--date')
    parser.add_argument('--md', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    events, invalid, duplicate = load(args.log)
    date = args.date or max((e['date'] for e in events), default=datetime.now(TZ).date().isoformat())
    calendar_date.fromisoformat(date)
    data = report(events, date, invalid, duplicate)
    text = markdown(data)
    for path, content in [(args.md, text), (args.json, json.dumps(data, ensure_ascii=False, indent=2) + '\n')]:
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
    print(text, end='')


if __name__ == '__main__':
    main()
