"""即时对战参数。数值、配招是本作改编，不冒充官方回合制规则。"""
import csv
import json
from functools import lru_cache
from pathlib import Path

TYPES={1:('一般','#c4c197'),2:('格斗','#d78461'),3:('飞行','#95bde1'),4:('毒','#b586cf'),5:('地面','#cfb16c'),6:('岩石','#ac9a71'),7:('虫','#99bd5b'),8:('幽灵','#9987c8'),9:('钢','#a3c4c1'),10:('火','#f2a05b'),11:('水','#69c9ec'),12:('草','#88d885'),13:('电','#f0da62'),14:('超能力','#f49db5'),15:('冰','#abeee4'),16:('龙','#a197ee'),17:('恶','#a89583'),18:('妖精','#eebcdd')}
MOVES={}
def m(id,name,type,kind,damage,cd,cost,range,**kw):
    MOVES[id]={'id':id,'name':name,'type':type,'kind':kind,'damage':damage,'cd':cd,'cost':cost,'range':range,'speed':500,'radius':8,'windup':.2,'recovery':.19,'color':TYPES[type][1],**kw}
m('watergun','水枪',11,'shot',10,.75,6,650,speed=550)
m('bubble','泡沫',11,'fan',8,1.4,9,430,speed=320,slow=1.0,radius=11)
m('waterpulse','水之波动',11,'shot',18,1.8,12,560,speed=410,slow=.7,radius=13)
m('hydropump','水炮',11,'beam',30,3.8,24,500,windup=.46)
m('aquajet','水流喷射',11,'rush',17,2.4,14,155,windup=.1)
m('surf','冲浪',11,'nova',24,4.8,24,125,windup=.5)
m('ember','火花',10,'fan',8,1.25,9,440,speed=440)
m('flamethrower','喷射火焰',10,'beam',23,3.0,18,340,windup=.32)
m('fireblast','大字爆炎',10,'zone',34,6,28,400,windup=.5,delay=.65,radius=100)
m('flamecharge','蓄能焰袭',10,'rush',19,2.8,15,150,windup=.16)
m('vinewhip','藤鞭',12,'melee',14,.95,8,108,windup=.15)
m('razorleaf','飞叶快刀',12,'fan',10,1.55,11,520,speed=560)
m('energyball','能量球',12,'shot',21,2.15,14,550,speed=390,radius=14)
m('solarbeam','日光束',12,'beam',38,6,28,620,windup=.8,recovery=.3)
m('synthesis','光合作用',12,'heal',23,12,25,0,windup=.7)
m('thundershock','电击',13,'shot',11,.85,7,580,speed=640)
m('thunderbolt','十万伏特',13,'beam',24,3,19,390,windup=.3)
m('thunder','打雷',13,'zone',32,5.5,26,420,windup=.38,delay=.75,radius=80)
m('quickattack','电光一闪',1,'rush',14,1.9,12,145,windup=.06)
m('agility','高速移动',14,'buff',0,9,16,0,windup=.15,duration=3.5,boost='speed')
m('icebeam','冰冻光束',15,'beam',22,3.2,19,420,windup=.32,slow=1.35)
m('icywind','冰冻之风',15,'fan',10,1.9,12,430,speed=360,slow=1.4)
m('blizzard','暴风雪',15,'zone',29,5.5,25,400,windup=.4,delay=.75,radius=110,slow=1.3)
m('tackle','撞击',1,'rush',11,1.4,8,90,windup=.1)
m('scratch','抓',1,'melee',12,.72,6,70,windup=.1)
m('brickbreak','劈瓦',2,'melee',18,1.2,10,79,windup=7/60,breakShield=True)
m('closecombat','近身战',2,'spin',27,3.7,23,83,windup=.22)
m('karatechop','空手劈',2,'melee',16,1.05,9,82,windup=.14)
m('machpunch','音速拳',2,'rush',15,1.8,11,120,windup=.08)
m('rockthrow','落石',6,'shot',18,1.6,11,520,speed=350,radius=12)
m('rockslide','岩崩',6,'zone',28,4.5,23,380,windup=.35,delay=.68,radius=95)
m('earthquake','地震',5,'nova',29,5.5,27,150,windup=.55)
m('mudshot','泥巴射击',5,'shot',13,1.4,9,490,speed=430,slow=1.1)
m('shadowball','暗影球',8,'shot',23,2.3,16,610,speed=480,radius=13)
m('lick','舌舔',8,'melee',12,1.2,9,98,windup=.15,slow=1.1)
m('hex','祸不单行',8,'zone',24,3.8,20,360,windup=.28,delay=.65,radius=75)
m('psychic','精神强念',14,'zone',29,4.8,24,400,windup=.35,delay=.65,radius=82)
m('psybeam','幻象光线',14,'beam',19,2.4,16,430,windup=.28)
m('confusion','念力',14,'shot',15,1.4,10,520,speed=430)
m('airslash','空气斩',3,'shot',20,1.85,13,570,speed=580,radius=11)
m('gust','起风',3,'fan',8,1.6,10,460,speed=450)
m('wingattack','翅膀攻击',3,'melee',19,1.45,11,102,windup=.18)
m('dragonbreath','龙息',16,'beam',23,3.0,19,355,windup=.31,slow=.7)
m('dragonpulse','龙之波动',16,'shot',26,3,19,580,speed=480,radius=14)
m('hyperbeam','破坏光线',1,'beam',43,7.5,32,640,windup=.85,recovery=.4)
m('poisonsting','毒针',4,'fan',7,1.5,10,450,speed=570)
m('sludgebomb','污泥炸弹',4,'shot',19,2.4,16,500,speed=380,radius=12)
m('bugbite','虫咬',7,'melee',15,1.2,9,75,windup=.13,leech=4)
m('signalbeam','信号光束',7,'beam',23,2.9,18,400,windup=.32)
m('protect','守住',1,'guard',30,6,13,0,windup=.08,duration=1.2)
m('recover','自我再生',1,'heal',25,13,27,0,windup=.7)
m('focusenergy','聚气',1,'buff',0,9,17,0,windup=.2,duration=4,boost='power')
m('rest','睡觉',14,'heal',35,16,30,0,windup=1.1,recovery=.7)
m('swift','高速星星',1,'fan',9,2.5,15,560,speed=510,count=5)
m('bite','咬住',17,'melee',18,1.3,11,75,windup=.14)
m('crunch','咬碎',17,'melee',25,2.4,17,83,windup=.26)
m('irontail','铁尾',9,'spin',24,2.8,18,100,windup=.3)
m('metalclaw','金属爪',9,'melee',15,1.0,8,80,windup=.12)
m('moonblast','月亮之力',18,'shot',26,3.0,20,540,speed=420,radius=14)
m('dazzlinggleam','魔法闪耀',18,'nova',24,4.5,23,120,windup=.38)
POOLS={
 1:['scratch','tackle','quickattack','swift','focusenergy','hyperbeam','rest'],
 2:['karatechop','machpunch','brickbreak','closecombat','focusenergy','quickattack'],
 3:['gust','wingattack','airslash','quickattack','agility','swift'],
 4:['poisonsting','sludgebomb','bite','hex','mudshot','protect'],
 5:['mudshot','earthquake','rockthrow','rockslide','tackle','brickbreak'],
 6:['rockthrow','rockslide','earthquake','tackle','brickbreak','protect'],
 7:['bugbite','signalbeam','poisonsting','agility','gust','tackle'],
 8:['shadowball','lick','hex','psychic','sludgebomb','agility'],
 9:['metalclaw','irontail','brickbreak','protect','quickattack','rockthrow'],
 10:['ember','flamecharge','flamethrower','fireblast','scratch','metalclaw'],
 11:['watergun','bubble','waterpulse','hydropump','aquajet','surf','icebeam','brickbreak'],
 12:['razorleaf','vinewhip','energyball','solarbeam','synthesis','sludgebomb'],
 13:['thundershock','quickattack','thunderbolt','thunder','agility','irontail'],
 14:['confusion','psybeam','psychic','recover','agility','shadowball'],
 15:['icywind','icebeam','blizzard','waterpulse','irontail','protect'],
 16:['dragonpulse','dragonbreath','wingattack','irontail','hyperbeam','agility'],
 17:['bite','crunch','shadowball','quickattack','agility','protect'],
 18:['moonblast','dazzlinggleam','swift','recover','psychic','protect']}
# All species share this multiplier; move damage/cooldowns/costs stay unchanged.
# B2: existing neutral 25-damage ordinary projectile takes 6–7 hits in the three fixtures.
# Attribute resistance/immunity and native baseHP differences are intentionally retained.
HP_MULTIPLIER = 1.5
DEFAULT_DIFFICULTY = "poke"

DIFFICULTIES=[
 {'id':'poke','name':'红白球级','color':'#dc6858','reaction':.36,'poll':.2,'dodge':.12,'lead':.12,'aimError':.14,'pressure':.12,'attackGap':.65,'reserve':10,'description':'出手较慢，偶尔闪避，适合熟悉招式。'},
 {'id':'great','name':'超级球级','color':'#5889c7','reaction':.23,'poll':.12,'dodge':.48,'lead':.48,'aimError':.065,'pressure':.45,'attackGap':.16,'reserve':16,'description':'会侧移、追击和闪避，开始抓出招空档。'},
 {'id':'ultra','name':'高级球级','color':'#5c626b','reaction':.16,'poll':.085,'dodge':.78,'lead':.73,'aimError':.03,'pressure':.75,'attackGap':.05,'reserve':22,'description':'会预瞄、换招、回体力和躲范围招式。'},
 {'id':'master','name':'大师球级','color':'#9870b9','reaction':.11,'poll':.06,'dodge':.94,'lead':.92,'aimError':.012,'pressure':1,'attackGap':0,'reserve':22,'description':'积极压迫，善用防守与回复；血量和伤害不加成。'}]

# 第二组60招：沿用已实现的11种动作机制；每个参数都有运行时代码与验收。
base_moves=set(MOVES)
m('bodyslam','泰山压顶',1,'rush',23,3.4,19,95,windup=.25,slow=.7)
m('doubleedge','舍身冲撞',1,'rush',34,4,24,155,windup=.2,recoil=.25)
m('headbutt','头锤',1,'melee',20,1.75,12,82,windup=.22)
m('return','报恩',1,'melee',21,1.8,12,83,windup=.18)
m('triattack','三重攻击',1,'fan',15,3.2,20,540,count=3,speed=460,slow=.7)
m('boomburst','爆音波',1,'nova',33,6,30,160,windup=.6)
m('explosion','大爆炸',1,'nova',60,14,42,180,windup=.9,recoil=.8)
m('rapidspin','高速旋转',1,'spin',14,1.7,10,82,windup=.13,cleanse=True)
m('waterfall','攀瀑',11,'rush',25,3.4,19,135,windup=.22)
m('brine','盐水',11,'shot',15,1.8,12,570,speed=470,execute=True)
m('scald','热水',11,'shot',18,2.3,16,520,speed=480)
m('aquatail','水流尾',11,'spin',25,2.9,18,110,windup=.3)
m('waterspout','喷水',11,'nova',37,6.5,29,155,windup=.55,hpScale=True)
m('aquaring','水流环',11,'heal',16,10,20,0,windup=.5)
m('firepunch','火焰拳',10,'melee',21,1.8,13,85,windup=.2)
m('firefang','火焰牙',10,'melee',17,1.45,10,77,windup=.14)
m('flamewheel','火焰轮',10,'rush',22,3.0,18,125,windup=.16)
m('heatwave','热风',10,'nova',26,4.6,24,128,windup=.4)
m('inferno','炼狱',10,'zone',38,7,31,420,windup=.5,delay=1,radius=88)
m('absorb','吸取',12,'melee',9,2,10,110,windup=.23,leech=7)
m('gigadrain','终极吸取',12,'beam',18,4.5,23,320,windup=.45,leech=12)
m('leafstorm','飞叶风暴',12,'fan',26,5.5,28,540,windup=.48,count=5,speed=570)
m('seedbomb','种子炸弹',12,'shot',24,2.65,18,460,speed=350,radius=14,windup=.3)
m('leafblade','叶刃',12,'melee',25,2.5,16,110,windup=.23)
m('thunderpunch','雷电拳',13,'melee',20,1.8,13,85,windup=.18)
m('spark','电光',13,'rush',20,2.6,16,150,windup=.12)
m('discharge','放电',13,'nova',26,4.8,24,125,windup=.4)
m('electroball','电球',13,'shot',19,2,13,580,speed=590,radius=11)
m('wildcharge','疯狂伏特',13,'rush',28,3.5,20,170,windup=.16,recoil=.25)
m('icepunch','冰冻拳',15,'melee',20,1.9,13,85,windup=.2,slow=1.1)
m('iceshard','冰砾',15,'shot',11,.85,7,480,speed=760,radius=6,windup=.13)
m('iciclecrash','冰柱坠击',15,'zone',27,4.5,22,390,windup=.3,delay=.6,radius=70,slow=.8)
m('freezedry','冷冻干燥',15,'beam',18,3.3,19,390,windup=.35,slow=1.3,waterEffective=True)
m('aurasphere','波导弹',2,'shot',24,2.5,17,550,speed=440,radius=14)
m('focusblast','真气弹',2,'shot',35,5.2,28,550,speed=350,radius=17,windup=.6)
m('drainpunch','吸取拳',2,'melee',17,2.7,17,82,windup=.2,leech=10)
m('reversal','起死回生',2,'melee',13,3.2,19,85,windup=.24,lowHP=True)
m('crosschop','十字劈',2,'melee',29,3.0,20,88,windup=.37)
m('stoneedge','尖石攻击',6,'zone',32,4.8,25,390,windup=.35,delay=.45,radius=53)
m('powergem','力量宝石',6,'shot',23,2.5,16,600,speed=580,radius=10)
m('rollout','滚动',6,'rush',22,3.1,17,165,windup=.13)
m('earthpower','大地之力',5,'zone',31,4.6,23,390,windup=.35,delay=.65,radius=86)
m('bulldoze','重踏',5,'nova',18,3.8,19,130,windup=.4,slow=1.25)
m('bonerush','骨棒乱打',5,'spin',23,2.8,17,112,windup=.25)
m('poisongas','毒瓦斯',4,'zone',7,6,20,330,windup=.38,delay=.5,radius=105)
m('poisonjab','毒击',4,'melee',19,1.9,13,87,windup=.2)
m('venoshock','毒液冲击',4,'shot',20,2.5,16,550,speed=500,venom=True)
m('zenheadbutt','意念头锤',14,'rush',24,3.2,18,140,windup=.22)
m('psychocut','精神利刃',14,'fan',16,2.5,17,510,speed=560)
m('storedpower','辅助力量',14,'shot',21,2.4,16,530,speed=430)
m('shadowsneak','影子偷袭',8,'rush',17,2.3,14,155,windup=.08)
m('shadowpunch','暗影拳',8,'melee',23,2.1,14,94,windup=.18)
m('phantomforce','潜灵奇袭',8,'rush',30,4.7,25,210,windup=.33,phaseRush=True)
m('peck','啄',3,'melee',12,.85,7,76,windup=.1)
m('bravebird','勇鸟猛攻',3,'rush',35,4.4,25,180,windup=.25,recoil=.3)
m('dragonclaw','龙爪',16,'melee',25,2.3,16,96,windup=.2)
m('dracometeor','流星群',16,'zone',41,7.5,33,440,windup=.6,delay=1,radius=120)
m('flashcannon','加农光炮',9,'beam',27,3.5,21,440,windup=.38)
m('darkpulse','恶之波动',17,'shot',25,2.8,18,580,speed=460,radius=13)
m('drainingkiss','吸取之吻',18,'melee',13,2.5,14,97,windup=.25,leech=10)
for id,mv in MOVES.items():
    if id not in base_moves:POOLS[mv['type']].append(id)

# 专属无伤动作不进入通用属性池，避免改变其他49只的配招。
m('splash','水溅跃',1,'splash',0,1,4,0,windup=.15,recovery=.4)
assert len(MOVES)==121

# 主角八招：长度单位为身体标定 nominalSize；只覆盖这八招的运行时参数。
HERO_MOVES = {
    'thunderbolt': {'kind': 'beam', 'range': 128, 'rangeBodies': 4, 'speed': 240,
                   'radius': 3, 'windup': .36, 'recovery': .25, 'anchor': 'cheek'},
    'quickattack': {'kind': 'rush', 'range': 120, 'rangeBodies': 3.6, 'rushSpeed': 600,
                    'windup': 0, 'recovery': .25, 'anchor': 'body'},
    'irontail': {'kind': 'melee', 'range': 42, 'rangeBodies': 1.3, 'windup': .28,
                'recovery': .28, 'anchor': 'tail'},
    'thunder': {'kind': 'zone', 'range': 120, 'rangeBodies': 3.6, 'radius': 26,
               'windup': .2, 'delay': .5, 'recovery': .5, 'anchor': 'ground'},
    'flamethrower': {'kind': 'beam', 'range': 170, 'rangeBodies': 3.5, 'speed': 240,
                    'radius': 10, 'windup': .42, 'recovery': .25, 'anchor': 'mouth'},
    'fireblast': {'kind': 'shot', 'range': 170, 'rangeBodies': 3.5, 'speed': 190,
                 'radius': 16, 'windup': .5, 'recovery': .25, 'anchor': 'mouth'},
    'dragonclaw': {'kind': 'melee', 'range': 44, 'rangeBodies': 1.1, 'windup': .28,
                  'recovery': .28, 'anchor': 'claw'},
    'airslash': {'kind': 'shot', 'range': 165, 'rangeBodies': 3.5, 'speed': 220,
                'radius': 8, 'windup': .36, 'recovery': .25, 'anchor': 'wing'},
}
from 招式特效.第2批参数 import RANGED_REVISIONS

for mid, revision in RANGED_REVISIONS.items():
    MOVES[mid].update(revision['runtime'])

HERO_ANCHORS = json.loads((Path(__file__).parent / '招式特效/主角锚点.json').read_text())
HERO_DEFAULTS = {
    25: ['thunderbolt', 'quickattack', 'irontail', 'thunder'],
    6: ['flamethrower', 'fireblast', 'dragonclaw', 'airslash'],
}
# 同类区域招 blizzard 29/5.5/25、stoneedge 32/4.8/25：打雷较小范围，0.7秒可躲。
MOVES['thunder'].update(damage=32, cd=5.5, cost=26)
for mid, runtime in HERO_MOVES.items():
    MOVES[mid].update(runtime, hero=True)


@lru_cache(maxsize=1)
def r200b_learnsets():
    """10-13 补充1：仅新增150只按任意世代可学∩原有120招；原50不变。"""
    root = Path(__file__).parent
    original = set(json.loads((root / '首发50.json').read_text())['ids'])
    selected = set(json.loads((root / '首发200.json').read_text())['ids']) - original
    with (root / '数值资料/Pi-20261011/learnset-audit.tsv').open(newline='') as f:
        learned = {int(r['dex']): r['runtime_move_ids'].split(',') if r['runtime_move_ids'] else []
                   for r in csv.DictReader(f, delimiter='\t')
                   if int(r['dex']) in selected and r['generation_group'].startswith('Any generation')}
    assert set(learned) == selected, 'Run scripts/R200b-可学采集.py first'
    assert all(len(v) == len(set(v)) and set(v) <= MOVES.keys() - {'splash'} for v in learned.values())
    return learned


def r200b_defaults(types, pool, learned, covers):
    """本系主攻 + 独立近身 + 副属性/覆盖/光束 + 守住，最少属性池补位。

    穷举三个攻击槽，先最小化不可学补位数，再按原属性池次序稳定选取。
    covers 是原有的全上场属性免疫检查；守住沿用通用规则。
    原作无变身的百变怪在调用处保留旧四招，不在这里伪造学招证据。
    """
    attack = lambda m: MOVES[m]['damage'] > 0 and MOVES[m]['kind'] not in ('heal', 'guard', 'buff', 'splash')
    available = list(dict.fromkeys(pool + learned))
    attacks = [m for m in available if attack(m)]
    rank = {m: i for i, m in enumerate(available)}
    learned = set(learned)
    primary = [m for m in attacks if MOVES[m]['type'] in types]
    near = [m for m in attacks if MOVES[m]['kind'] in ('melee', 'rush', 'spin')]
    best = None
    for a in primary:
        for b in near:
            if b == a:
                continue
            for c in attacks:
                if c in (a, b):
                    continue
                ta, tb, tc = (MOVES[m]['type'] for m in (a, b, c))
                score = (sum(m not in learned for m in (a, b, c)),
                         sum(m not in learned and MOVES[m]['type'] not in types for m in (a, b, c)),
                         types.index(ta),
                         0 if tc in types and tc != ta else 1,
                         rank[a], 0 if tb in types else 1, rank[b],
                         0 if tc not in (ta, tb) else 1,
                         0 if MOVES[c]['kind'] in ('beam', 'zone', 'nova', 'shot', 'fan') else 1,
                         rank[c])
                if (best is None or score < best[0]) and covers([a, b, c]):
                    best = (score, [a, b, c, 'protect'])
    assert best is not None, (types, learned)
    return best[1]


def roster_metadata(rows):
    result=[]
    # 官方属性免疫关系；避免推荐四招在某个已收录对手身上全部无效。
    immune={1:{8},2:{8},4:{9},5:{3},8:{1},13:{5},14:{17},16:{18}}
    combos={tuple(c['types']) for c in rows}
    def covers(ids):
        return all(any(not immune.get(MOVES[m]['type'],set()).intersection(target) for m in ids if MOVES[m]['damage']>0 and MOVES[m]['kind'] not in ('heal','guard','buff')) for target in combos)
    for row in rows:
        n=row['id'];ts=row['types'];pool=[]
        for t in ts:
            for move in POOLS[t]:
                if move not in pool:pool.append(move)
        for move in ['tackle','protect','quickattack','brickbreak','bite']:
            if move not in pool:pool.append(move)
        defaults=[pool[0],next((x for x in pool if MOVES[x]['kind'] in ('melee','rush','spin')),pool[1]),next((x for x in pool if MOVES[x]['kind'] in ('beam','zone','nova') and x!=pool[0]),pool[2]),'protect']
        used_types={MOVES[x]['type'] for x in defaults[:2]}
        coverage=next((x for x in pool if MOVES[x]['damage']>0 and MOVES[x]['kind'] not in ('guard','heal','buff') and MOVES[x]['type'] not in used_types and MOVES[x]['type']!=1),None)
        if coverage:defaults[2]=coverage
        defaults=list(dict.fromkeys(defaults))
        for move in pool:
            if len(defaults)==4:break
            if move not in defaults:defaults.append(move)
        if n==7:defaults=['watergun','brickbreak','aquajet','protect']
        if not covers(defaults):
            for move in pool:
                if move not in defaults[:2] and move!='protect' and covers(defaults[:2]+[move]):
                    defaults[2]=move;break
        if n in HERO_DEFAULTS:
            defaults = HERO_DEFAULTS[n].copy()
            for move in defaults:
                if move not in pool:
                    pool.append(move)
        # R200b 授权仅新150只：原50默认招、可选池、数值和动画完全不变。
        learned = r200b_learnsets().get(n)
        if learned is not None:
            if n != 132:  # 原作仅变身，暂用一般系；不声称旧四招可学。
                defaults = r200b_defaults(ts, pool, learned, covers)
            pool = list(dict.fromkeys(pool + learned))
        flags=[]
        if n==129:
            pool=['splash'];defaults=['splash'];flags=['无伤配招']
        assert '无伤配招' in flags or covers(defaults)
        char={k:row[k] for k in ['id','name','types','hp','speed','scale','credits']};char.update(learnset=pool,defaultMoves=defaults,nativeFloatOrBob=row.get('nativeFloatOrBob',False))
        if flags:char['flags']=flags
        if str(n) in HERO_ANCHORS:
            char['moveAnchors'] = HERO_ANCHORS[str(n)]
        if n==7:char.update(hp=100,speed=185)
        char['baseHP'] = char['hp']
        char['hp'] = int(char['baseHP'] * HP_MULTIPLIER + 0.5)
        result.append(char)
    return result
