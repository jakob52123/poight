"""逐机制、逐招式、UI、离线、性能与实际AI行为验收。失败保留证据，不自动发布。"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import argparse,hashlib,json,math,time
from datetime import datetime,timezone
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--url',default=(ROOT/'候选试玩.html').as_uri());ap.add_argument('--tag',default='候选');a=ap.parse_args()
checks=[];errors=[];requests=[];failed_requests=[];bench={};URL=a.url;tested_sha=None

def check(name,value,details=None):
    checks.append({'name':name,'passed':bool(value),'details':details})
    if not value:raise AssertionError(name+': '+repr(details))
def save():
    report={'url':URL,'tag':a.tag,'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'errors':errors,'failedRequests':failed_requests,'benchmarks':bench,'candidateSHA256':hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),'testedHTMLSHA256':tested_sha,'scope':'真实浏览器；技能全部实测；全资源图像检查另见构建核验。技术测试不是玩家手感/声音听审或所有物种平衡胜率证明。'}
    content=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    (ROOT/f'完整版验收-{a.tag}.json').write_text(content)
    history=ROOT/'验收记录';history.mkdir(exist_ok=True)
    (history/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+a.tag+'.json')).write_text(content)

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True)
    context=browser.new_context(viewport={'width':1440,'height':900},device_scale_factor=1)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url));page.on('requestfailed',lambda r:failed_requests.append({'url':r.url,'failure':r.failure}))
    def call(code,arg=None):return page.evaluate(code,arg)
    def wait_expression(expr,timeout=30000):
        # 测试侧CDP读取，避免Playwright旧轮询器使用eval触发正式CSP；不放宽游戏策略。
        deadline=time.monotonic()+timeout/1000
        while time.monotonic()<deadline:
            if page.evaluate('()=>('+expr+')'):return
            page.wait_for_timeout(35)
        raise TimeoutError(expr)
    page.wait_for_function=wait_expression
    def snap():return call('()=>__waterTest.snapshot()')
    def step(t):call('(t)=>__waterTest.step(t)',t)
    def setup(**kw):call('(s)=>__waterTest.arrange(s)',kw)
    def reset(ai=False):
        for k in ['w','a','s','d','j','k','l','i','ArrowUp','ArrowDown','ArrowLeft','ArrowRight']:page.keyboard.up(k)
        call('()=>__waterTest.reset(true)');setup(ai=ai)
    def hold(key,t):page.keyboard.down(key);step(t);page.keyboard.up(key)
    def cast(id,side='player'):return call('([side,id])=>__waterTest.cast(side,id)',[side,id])
    def equip(id,side='player'):
        ids=[id]+[v for v in ['watergun','brickbreak','protect','quickattack'] if v!=id][:3];call('([side,ids])=>__waterTest.equip(side,ids)',[side,ids])
    def choose(p=7,e=7,tier='great'):
        return call('([p,e,tier])=>{const r=__waterTest.catalog().roster,me=r.find(c=>c.id===p),ai=r.find(c=>c.id===e);return __waterTest.select({player:p,enemy:e,playerMoves:me.defaultMoves,enemyMoves:ai.defaultMoves,tier});}',[p,e,tier])
    try:
        response=page.goto(URL+'?test=1',wait_until='load');tested_sha=hashlib.sha256(response.body()).hexdigest();check('实际加载页面与候选构建SHA一致',tested_sha==hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest());page.wait_for_function('window.__waterTest?.snapshot().artReady',timeout=30000)
        catalog=call('()=>__waterTest.catalog()');roster=catalog['roster'];moves=catalog['moves'];roster_ids={c['id'] for c in roster}
        check('严格只开放指定50只，不继续扩充',len(roster)==50 and roster_ids==set(json.loads((ROOT/'首发50.json').read_text())['ids']))
        check('121招覆盖12种实际机制（含无伤水溅跃）',len(moves)==121 and len({m['kind'] for m in moves.values()})==12)
        check('四档中文名称完全符合指定',[t['name'] for t in catalog['tiers']]==['红白球级','超级球级','高级球级','大师球级'])
        check('所有默认配招1–4招唯一、可学、有定义',all(1<=len(c['defaultMoves'])<=4 and len(c['defaultMoves'])==len(set(c['defaultMoves'])) and set(c['defaultMoves'])<=set(c['learnset'])<=set(moves) for c in roster))
        check('所有角色六类动作接口完整',all(set(c)=={'idle','walk','shoot','melee','hurt','dash'} for c in catalog['art'].values()))
        choose();reset();s=snap();check('所有四槽都能使用',page.locator('button.skill').count()==4)
        check('血量/体力独立三条可访问进度条',page.locator('[role="progressbar"]').count()==3 and s['player']['hp']==100 and s['player']['stamina']==100)
        hold('d',.4);s=snap();straight=s['player']['x']-215;check('普通行走185px/s且不扣体力',abs(straight-74)<.05 and s['player']['stamina']==100,s['player'])
        step(.2);check('松键即停',abs(snap()['player']['x']-s['player']['x'])<.02)
        reset();page.keyboard.down('d');hold('w',.4);page.keyboard.up('d');s=snap();check('斜向速度不叠加',abs(math.hypot(s['player']['x']-215,s['player']['y']-280)-74)<.05)
        reset();hold('ArrowLeft',2);check('方向键支持/世界边界',snap()['player']['x']==55)
        reset();page.keyboard.down('d');step(.04);f1=snap()['player']['animFrame'];step(.21);f2=snap()['player']['animFrame'];page.keyboard.up('d');check('真实行走帧发生切换',f1!=f2,[f1,f2])
        reset();hold('d',.05);step(.08);page.keyboard.down('d');s=snap();x=s['player']['x'];check('双击方向一次扣22并进入保护',s['player']['dashing'] and s['player']['stamina']==78 and s['player']['protected'])
        step(.10);check('闪避位移速度590',abs(snap()['player']['x']-x-59)<.1)
        step(.1);page.keyboard.up('d');check('闪避如期结束',not snap()['player']['dashing']);step(1.5);check('体力延迟恢复且不越界',snap()['player']['stamina']==100)
        reset();page.keyboard.down('d');step(.1);page.keyboard.down('d');step(.1);page.keyboard.up('d');check('系统键盘连发不误触闪避',snap()['player']['dodges']==0)
        reset();setup(player={'stamina':0});check('体力不足无法闪避',not call('()=>__waterTest.dash("player",1,0)'));check('不出现负体力',snap()['player']['stamina']==0)
        reset();hold('a',.05);page.keyboard.down('j');step(.08);s=snap();check('背向后出招自动瞄准而非追身',s['player']['attack']['id']=='watergun' and abs(s['player']['attack']['aim'])<.01 and s['player']['x']<215)
        check('水枪起手未发射即扣6，血量不动',s['player']['shots']==0 and s['player']['stamina']==94 and s['player']['hp']==100)
        step(.14);page.keyboard.up('j');s=snap();check('过起手后发射',s['player']['shots']==1 and len(s['bullets'])==1)
        direction=(s['bullets'][0]['ux'],s['bullets'][0]['uy']);setup(enemy={'y':420});step(.08);s=snap();check('弹道不追踪',s['bullets'] and abs(s['bullets'][0]['ux']-direction[0])<1e-9 and abs(s['bullets'][0]['uy']-direction[1])<1e-9)
        reset();hold('j',2.99);s=snap();check('按住水枪尊重0.75秒CD',s['player']['shots']==4 and s['player']['spent']==24,s['player'])
        reset();cast('watergun');step(.08);call('()=>__waterTest.dash("player",0,1)');step(.3);s=snap();check('闪避取消起手，不退资源或CD',s['player']['shots']==0 and s['player']['spent']==28 and s['player']['cool']['watergun']>0)
        reset();setup(enemy={'x':280,'y':280});hold('k',.25);s=snap();check('劈瓦近身伤害且不自动靠近',s['enemy']['hp']<100 and abs(s['player']['x']-215)<.01 and s['player']['cool']['brickbreak']>0)
        reset();hold('k',.25);check('远处挥空，没有自动接近',snap()['enemy']['hp']==100 and snap()['player']['x']==215)
        reset();setup(player={'x':340,'y':180},enemy={'x':520,'y':180});hold('j',1);check('岩石挡水枪',snap()['enemy']['hp']==100)
        reset();setup(player={'x':363,'y':180},enemy={'x':500,'y':180});hold('d',1);s=snap();check('人不能穿岩石',s['player']['x']<=376.1,s['player'])
        call('()=>__waterTest.dash("player",1,0)');step(.2);check('闪避不能穿岩石',snap()['player']['x']<=376.1)
        reset();setup(player={'x':310,'y':380},enemy={'x':460,'y':380});hold('j',1);check('绿篱挡弹道',snap()['enemy']['hp']==100)
        reset();setup(player={'x':600,'y':450},enemy={'x':795,'y':450});hold('j',1);check('树木挡弹道',snap()['enemy']['hp']==100)
        reset();setup(player={'x':215,'y':280});page.keyboard.down('l');step(.30);page.keyboard.up('l');s=snap();check('第三槽L是真实突进',s['player']['x']>250 and s['player']['cool']['aquajet']>0)
        reset();hold('i',.15);check('第四槽I产生护盾',snap()['player']['shield']==30)
        # Every move goes through actual attack scheduling, contact/physics and state changes.
        outcomes=[]
        for id,m in moves.items():
            reset();equip(id);setup(player={'x':215,'y':280,'hp':70},enemy={'x':280,'y':280})
            ok=cast(id);step(m['windup']+(m.get('delay',0) if m['kind']=='zone' else 0)+.29);s=snap()
            if m['kind']=='heal':effect=s['player']['hp']>70
            elif m['kind']=='guard':effect=s['player']['shield']==m['damage']
            elif m['kind']=='buff':effect=s['player']['buffs'][m['boost']]>0
            else:effect=s['enemy']['hp']<100
            check('招式实际生效：'+m['name'],ok and effect,{'id':id,'kind':m['kind'],'playerHP':s['player']['hp'],'enemyHP':s['enemy']['hp'],'shield':s['player']['shield']})
            check('CD与体力实际消耗：'+m['name'],s['player']['spent']==m['cost'] and s['player']['cool'][id]>0)
            outcomes.append({'id':id,'enemyDamage':100-s['enemy']['hp'],'playerHP':s['player']['hp']})
        bench['allMoves']=outcomes
        reset();equip('scald');setup(enemy={'x':280,'y':280});cast('scald');step(.35);s=snap();hp=s['enemy']['hp'];check('热水附加真实灼伤',s['enemy']['burn'] is not None);step(.8);check('持续状态继续扣血',snap()['enemy']['hp']<hp)
        reset();equip('icebeam');setup(enemy={'x':320,'y':280});cast('icebeam');step(.4);check('冰招真实施加减速',snap()['enemy']['slow']>1)
        reset();equip('protect','enemy');setup(enemy={'x':280,'y':280});cast('protect','enemy');step(.12);cast('watergun');step(.4);check('守住真实吸收伤害',snap()['enemy']['hp']==100 and snap()['enemy']['shield']<30)
        reset();equip('protect','enemy');setup(enemy={'x':280,'y':280});cast('protect','enemy');step(.12);cast('brickbreak');step(.2);check('劈瓦破盾且造成伤害',snap()['enemy']['shield']==0 and snap()['enemy']['hp']<100)
        reset();equip('recover');setup(player={'hp':40},enemy={'x':280,'y':280});cast('recover');step(.15);cast('brickbreak','enemy');step(.6);check('回复起手能被打断',snap()['player']['hp']<40 and snap()['player']['cool']['recover']>0)
        reset();equip('agility');cast('agility');step(.4);x=snap()['player']['x'];hold('d',.3);check('高速移动收招后真实增加30%移速',abs(snap()['player']['x']-x-185*.3*1.3)<.1)
        reset();equip('doubleedge');setup(player={'hp':70},enemy={'x':280,'y':280});cast('doubleedge');step(.45);check('舍身招真实反伤',snap()['player']['hp']<70)
        reset();equip('phantomforce');cast('phantomforce');step(.36);check('潜灵突进有真实短保护',snap()['player']['protected'])
        def measured_damage(id,own_hp=100,target_hp=100):
            reset();equip(id);setup(player={'hp':own_hp},enemy={'x':280,'y':280,'hp':target_hp});cast(id);step(moves[id]['windup']+.3);return target_hp-snap()['enemy']['hp']
        check('盐水对残血真正增伤',measured_damage('brine',target_hp=40)>measured_damage('brine'))
        check('起死回生随自身残血增伤',measured_damage('reversal',own_hp=20)>measured_damage('reversal'))
        check('喷水威力随自身血量变化',measured_damage('waterspout',own_hp=100)>measured_damage('waterspout',own_hp=20))
        check('冷冻干燥确实克制水，不沿用冰系抵抗',measured_damage('freezedry')>measured_damage('icebeam')*2)
        reset();equip('recover');check('满血回复不骗取体力或CD',not cast('recover') and snap()['player']['spent']==0 and snap()['player']['cool']['recover']==0)
        reset();equip('rapidspin');equip('scald','enemy');setup(enemy={'x':280,'y':280});cast('scald','enemy');step(.55);check('清异常测试前确有灼伤',snap()['player']['burn'] is not None);cast('rapidspin');step(.3);check('高速旋转真实解除异常',snap()['player']['burn'] is None)
        baseline=measured_damage('venoshock');reset();equip('poisonsting');setup(enemy={'x':280,'y':280});cast('poisonsting');step(.55);setup(enemy={'hp':100});equip('venoshock');cast('venoshock');step(.4);check('毒液冲击确实利用已有中毒',100-snap()['enemy']['hp']>=baseline*1.5)
        reset();setup(enemy={'hp':1,'x':280,'y':280});cast('brickbreak');step(.3);s=snap();check('KO结算胜利且冻结战斗',s['phase']=='over' and s['outcome']=='win' and s['enemy']['hp']==0 and not s['bullets']);time0=s['elapsed'];step(2);check('结算后时间和战斗冻结',snap()['elapsed']==time0)
        page.screenshot(path=str(ROOT/f'完整版-胜负-{a.tag}.png'))
        page.keyboard.press('r');check('R重置双方状态',snap()['phase']=='idle' and snap()['player']['hp']==100 and snap()['enemy']['hp']==100)
        reset();page.keyboard.press('Escape');s=snap();step(.5);check('Esc暂停冻结所有战斗',s['phase']=='paused' and snap()['elapsed']==s['elapsed']);page.keyboard.press('Escape');check('Esc继续',snap()['phase']=='playing')
        reset();page.evaluate('window.dispatchEvent(new Event("blur"))');check('离开窗口安全暂停',snap()['phase']=='paused')
        # Difficulty fairness and observed-projectile reaction.
        fairness=[];dodge=[];idle=[]
        for t in catalog['tiers']:
            choose(tier=t['id']);reset();setup(enemy={'x':280,'y':280});cast('watergun');step(.45);s=snap();fairness.append((s['player']['maxHP'],s['enemy']['maxHP'],100-s['enemy']['hp'],s['player']['spent']))
            reset(ai=True);setup(player={'x':215,'y':280},enemy={'x':585,'y':280});call('()=>__waterTest.injectWater({owner:"player",x:425,y:280,ux:1,uy:0})');step(.085);first=snap()['enemy']['dodges'];step(.18);s=snap();dodge.append({'tier':t['id'],'beforeReaction':first,'after':s['enemy']['dodges'],'hp':s['enemy']['hp']})
            reset(ai=True);step(45);s=snap();idle.append({'tier':t['id'],'outcome':s['outcome'],'seconds':s['elapsed'],'AI':s['ai']})
            check(t['name']+'能主动打败静止玩家',s['outcome']=='loss',idle[-1])
        bench.update(difficultyFairness=fairness,dodgeReaction=dodge,idlePlayer=idle)
        check('四档不暗加血量/伤害/体力优势',len(set(fairness))==1,fairness)
        check('所有等级都不提前读取弹道反应',all(x['beforeReaction']==0 for x in dodge),dodge)
        check('大师球实战闪避能力高于红白球',dodge[-1]['after']>dodge[0]['after'],dodge)
        choose(tier='master');reset(ai=True);setup(player={'x':1440,'y':780},enemy={'x':165,'y':180});d0=math.hypot(1275,600);step(3);s=snap();d1=math.hypot(s['player']['x']-s['enemy']['x'],s['player']['y']-s['enemy']['y']);check('AI在大地图追击并绕障碍',d1<d0-250 and s['ai']['pathSearches']>0 and s['ai']['pursuitDashes']>0,s['ai'])
        check('镜头跟随且不会露出世界外',0<=s['camera']['x']<=1600-s['viewport']['width']+.01 and 0<=s['camera']['y']<=1000-s['viewport']['height']+.01 and s['camera']['x']>100,s['camera'])
        page.screenshot(path=str(ROOT/f'完整版-追击-{a.tag}.png'))
        # Actual UI, focus safety, loadout validation, filters and persistence.
        page.locator('#setupButton').click();check('换精灵时暂停',snap()['phase']=='paused' and page.locator('#setup').evaluate('(e)=>e.open'))
        page.locator('#search').fill('皮卡丘');check('中文搜索与真实卡片',page.locator('.mon').count()==1 and page.locator('.mon').get_attribute('data-id')=='25')
        page.locator('.mon').click();check('选角色自动更新真实配招/预览',page.locator('#selectedName').inner_text()=='皮卡丘' and page.locator('#moveSlots button').count()==4)
        page.locator('#toggleLoadout').click();page.locator('#moveChoice0').click();card=page.locator('.move-card:not([disabled]):not([aria-pressed="true"])').first;chosen=card.get_attribute('data-move');card.click();check('卡片配招实际替换槽位',page.locator('#moveChoice0').get_attribute('data-move')==chosen)
        page.locator('#moveChoice1').click();check('其他槽位已装招式禁止重复',page.locator(f'.move-card[data-move="{chosen}"]').is_disabled());page.locator('.ai-options summary').click()
        page.locator('#difficulty button[data-tier="ultra"]').click();page.locator('#toggleLoadout').click();page.locator('#pickEnemyPanel').click();page.locator('#search').fill('006');check('零填充编号精确搜索，不混入16/26等',page.locator('.mon[data-id="6"]').count()==1 and page.locator('.mon').count()==1);page.locator('.mon[data-id="6"]').click();page.locator('#startBattle').click();page.wait_for_function('__waterTest.snapshot().phase==="versus"');check('VS确认时战斗尚未推进',snap()['elapsed']==0 and page.locator('#vsEnemyName').inner_text()=='喷火龙');page.locator('#vsContinue').click();page.wait_for_function('__waterTest.snapshot().phase==="playing"&&__waterTest.snapshot().player.id===25');s=snap();check('两只不同角色/自定义四招/强度实际进入战斗',s['player']['id']==25 and s['enemy']['id']==6 and s['player']['moves'][0]==chosen and s['profile']['tier']=='ultra')
        step(.12);page.screenshot(path=str(ROOT/f'完整版-对战-{a.tag}.png'))
        page.locator('#setupButton').click();page.locator('#search').fill('jkli');step(.2);check('搜索框不触发攻击',not snap()['player']['attack'] and snap()['phase']=='paused');page.locator('#search').fill('不存在的怪物');check('空搜索有提示',page.locator('.empty-results').count()==1)
        page.locator('#search').fill('');page.locator('#typeFilterToggle').click();page.locator('#typeChoices button[data-type="13"]').click();check('属性筛选准确',all(13 in next(c['types'] for c in roster if c['id']==int(v)) for v in page.locator('.mon').evaluate_all('(a)=>a.map(e=>e.dataset.id)')))
        page.locator('#typeFilterToggle').click();page.locator('#typeChoices button[data-type=""]').click();page.locator('#search').fill('');check('首发50头像同屏矩阵，无多余翻页',page.locator('.mon').count()==50 and not page.locator('#nextPage').is_visible())
        page.screenshot(path=str(ROOT/f'完整版-选角-{a.tag}.png'));page.locator('#closeSetup').click();check('取消配置不影响现役角色',snap()['player']['id']==25 and snap()['profile']['tier']=='ultra')
        for vw,vh in [(1920,1080),(1440,900),(1280,720),(900,600),(844,390),(390,844)]:
            page.set_viewport_size({'width':vw,'height':vh});page.wait_for_function('Math.abs(__waterTest.snapshot().viewport.width/__waterTest.snapshot().viewport.height-innerWidth/innerHeight)<.01',timeout=3000);rect=page.locator('#game').bounding_box();s=snap();overflow=call('()=>({x:document.documentElement.scrollWidth>innerWidth,y:document.documentElement.scrollHeight>innerHeight})')
            check(f'{vw}×{vh}铺满无滚动/拉伸',rect['width']==vw and rect['height']==vh and rect['x']==rect['y']==0 and abs(s['viewport']['width']/s['viewport']['height']-vw/vh)<.01 and not any(overflow.values()),{'canvas':rect,'viewport':s['viewport'],'overflow':overflow})
            check(f'{vw}×{vh}调整窗口不改变世界',s['world']=={'width':1600,'height':1000})
            page.locator('#setupButton').click();page.screenshot(path=str(ROOT/f'完整版-布局{vw}x{vh}-{a.tag}.png'));button=page.locator('#startBattle').bounding_box();check(f'{vw}×{vh}开始按钮始终可见',button['y']>=0 and button['y']+button['height']<=vh+1,button);page.locator('#closeSetup').click()
        page.set_viewport_size({'width':1440,'height':900});page.locator('#fullscreen').click();page.wait_for_timeout(200);check('调用浏览器真正全屏API',call('()=>!!document.fullscreenElement'));page.locator('#fullscreen').click();page.wait_for_timeout(100);check('可退出全屏',not call('()=>!!document.fullscreenElement'))
        page.locator('#sound').click();check('声音开启可见',page.locator('#sound').get_attribute('aria-pressed')=='true');page.locator('#sound').click();check('声音关闭可见',page.locator('#sound').get_attribute('aria-pressed')=='false')
        samples=[x for x in [1,6,7,25,94,95,129,143,149,150,151,201,248,249,282,384,386,448,493,658,800,888,1000,1025] if x in roster_ids]
        for id in samples:
            check(f'角色#{id:03}六动作在浏览器解码',call('(id)=>__waterTest.preload(id)',id))
        check('动画缓存有界，非全图鉴解码',len(snap()['cachedCharacters'])<=6,snap()['cachedCharacters'])
        # Live rAF timing: distinguish CPU submission from actual display FPS.
        page.goto(URL+'?observe=1',wait_until='load');page.wait_for_function('__waterTest.snapshot().artReady&&document.querySelector("#setup").open');page.locator('#startBattle').click();page.locator('#vsContinue').click();page.keyboard.down('s');s0=snap();start=time.monotonic();page.wait_for_timeout(1500);s1=snap();wall=time.monotonic()-start;page.keyboard.up('s');sim=s1['elapsed']-s0['elapsed'];bench['realRAF']={'wallSeconds':wall,'simSeconds':sim,'deliveredFPS':(s1['frame']-s0['frame'])/wall,'cpuP95Ms':s1['timing']['cpuP95Ms'],'cpuMaxMs':s1['timing']['cpuMaxMs']}
        check('真实帧循环按墙钟推进，不再低fps慢动作',abs(sim-wall)<.18,bench['realRAF']);check('绘制+仿真CPU P95低于16ms',s1['timing']['cpuP95Ms']<16,bench['realRAF'])
        check('观测模式只读',call('()=>Object.keys(__waterTest).join(",")')=='snapshot')
        page.goto(URL,wait_until='load');page.wait_for_function('document.querySelector("#setup").open');check('正常入口无调试后门',not call('()=>"__waterTest" in window'))
        check('本地保存配招能恢复',page.locator('#draftPlayerName').inner_text()=='皮卡丘' and page.locator('#selectedName').inner_text()=='皮卡丘')
        if urlsplit(URL).scheme=='file':check('双击HTML离线直接运行',page.locator('#roster .mon').count()>0)
        host=urlsplit(URL).netloc;external=[u for u in requests if urlsplit(u).scheme in ('http','https') and urlsplit(u).netloc!=host];check('运行无外部模型或素材网络请求',not external,external)
        check('浏览器无脚本错误',not errors,errors);check('运行无素材请求失败',not failed_requests,failed_requests)
        save();print(json.dumps({'passed':len(checks),'errors':errors,'roster':len(roster),'moves':len(moves),'benchmarks':{k:v for k,v in bench.items() if k!='allMoves'}},ensure_ascii=False,indent=2))
    except Exception:
        page.screenshot(path=str(ROOT/f'完整版-失败-{a.tag}.png'));save();raise
    finally:browser.close()
