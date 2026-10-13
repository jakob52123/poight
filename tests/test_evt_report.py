"""Deterministic report coverage without a browser or network."""
import base64
import json
import unittest
from urllib.parse import urlencode

from scripts.埋点日报 import FIELDS, distribution, parse_line, report


class ReportTest(unittest.TestCase):
    def event(self, name, date='2026-10-13', device='one', session='s', tick=0, **props):
        defaults = {key: 0 for key in FIELDS[name].split()}
        if name == 'page_view':
            defaults.update(ref='github.com', src='github', utm='', dt='desktop',
                            w=1440, h=900, o='landscape', lang='zh-CN', sa=False, rv=False)
        defaults.update(props)
        payload = base64.urlsafe_b64encode(json.dumps(defaults).encode()).decode().rstrip('=')
        args = urlencode({'v': 1, 'e': name, 'd': device, 's': session,
                          't': tick, 'b': 'eb38429a', 'p': payload})
        return parse_line(json.dumps({'ts': date+'T12:00:00+08:00', 'args': args}))

    def test_nginx_equals_jsonl_and_midnight(self):
        e = self.event('page_view')
        nginx = f'2026-10-12T16:00:01Z localhost "{e["raw"]}"'
        self.assertEqual(parse_line(nginx)['date'], '2026-10-13')
        self.assertEqual(parse_line(nginx)['p'], e['p'])

    def test_ordered_funnel_not_false_positive(self):
        e = [self.event('page_view'), self.event('battle_ready', tick=10, ms=10, kb=1),
             self.event('select_ready', tick=20, ms=20, kb=1),
             self.event('battle_start_click', tick=30, a=7, c=4, m='arena', l='easy',
                        x=['bubble'], y=['ember'], z=True)]
        r = report(e, '2026-10-13')
        self.assertEqual([f['n'] for f in r['funnel']], [1, 1, 1, 0, 0, 0, 0])
        self.assertEqual(r['funnel'][1]['ms']['median'], 20)

    def test_retention_cohorts_and_existing_devices(self):
        e = [self.event('page_view', date='2026-10-06', device='seven', session='a'),
             self.event('page_view', date='2026-10-12', device='next', session='b'),
             self.event('page_view', device='seven', session='c', rv=True),
             self.event('page_view', device='next', session='d', rv=True),
             self.event('page_view', date='2026-10-12', device='old', session='e', rv=True)]
        r = report(e, '2026-10-13')
        self.assertEqual(r['retention']['d1']['base'], 1)
        self.assertEqual(r['retention']['d1']['rate'], 1)
        self.assertEqual(r['retention']['d7']['base'], 1)
        self.assertEqual(r['retention']['d7']['rate'], 1)

    def test_rematch_attribution_move_counts_and_wins(self):
        e = [self.event('page_view'),
             self.event('select_ready', tick=10, ms=10, kb=1),
             self.event('battle_start_click', tick=20, a=7, c=4, m='arena', l='easy',
                        x=['bubble'], y=['ember'], z=True),
             self.event('battle_ready', tick=30, ms=10, kb=5),
             self.event('first_input', tick=40, ms=10, i='keyboard'),
             self.event('battle_end', tick=50, r='win', sec=10, h=90, hit=2, hurt=1, ev=1,
                        u=[[2], [3]], f=60, pa=False),
             self.event('rematch', tick=60, ms=10),
             self.event('battle_ready', tick=70, ms=0, kb=0),
             self.event('battle_end', tick=80, r='lose', sec=10, h=0, hit=2, hurt=1, ev=1,
                        u=[[4], [5]], f=50, pa=True)]
        r = report(e, '2026-10-13')
        self.assertEqual(r['north_star'], 2)
        self.assertEqual(r['content']['moves']['player']['bubble'], 6)
        self.assertEqual(r['content']['pokemon_win_rate']['player:7']['rate'], .5)
        self.assertEqual(r['funnel'][-1]['n'], 1)
        self.assertEqual(r['games_per_device']['mean'], 2)

    def test_empty_and_interpolated_p90(self):
        r = report([], '2026-10-13')
        self.assertEqual(r['north_star'], 0)
        self.assertIsNone(r['retention']['d7']['rate'])
        self.assertEqual(distribution([10, 20]), {'n': 2, 'median': 15, 'p90': 19})

    def test_reject_bad_protocol_and_missing_fields(self):
        e = self.event('page_view')
        with self.assertRaises(ValueError):
            parse_line(json.dumps({'ts': '2026-10-13T12:00:00+08:00',
                                   'args': e['raw'].replace('v=1', 'v=2')}))
        with self.assertRaises(ValueError):
            parse_line('garbage')


if __name__ == '__main__':
    unittest.main()
