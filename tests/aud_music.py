"""AUD streaming acceptance, called by 验收-战斗音乐.py (serial browsers)."""
import base64
import json
import os
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wait(page, fn, seconds=6):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        value = page.evaluate(fn)
        if value:
            return value
        page.wait_for_timeout(25)
    return None


def external_main(check, checks, errors, out):
    from playwright.sync_api import sync_playwright
    from 工具_外部BGM响度 import audit
    url = os.environ['POIGHT_TEST_URL'].rstrip('/')
    tracks = json.loads((ROOT / '素材/音乐/外部BGM.json').read_text())
    observations = {}
    with sync_playwright() as pw:
        for engine in ['chromium', 'webkit']:
            browser = getattr(pw, engine).launch(headless=True)
            context = browser.new_context(viewport={'width':1440,'height':900})
            context.add_init_script('''(()=>{
              window.mediaAssignments=[];
              const d=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'src');
              Object.defineProperty(HTMLMediaElement.prototype,'src',{...d,set(v){
                mediaAssignments.push({src:v,artReady:window.__waterTest?.snapshot().artReady,time:performance.now()});
                d.set.call(this,v);
              }});
            })();''')
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            requests = []
            page.on('request', lambda r: requests.append({'url':r.url,'time':time.monotonic()}))
            page.goto(url + '/')
            wait(page, '()=>document.querySelector("#setup").open')
            check(engine+' 正常新用户默认随机9首、开、40%',
                  page.locator('#musicTrack').input_value()=='random' and
                  page.locator('#musicToggle').text_content()=='音乐：开' and
                  page.locator('#musicVolume').input_value()=='40')
            check(engine+' 正常入口不暴露额外候选/报警策略',
                  page.evaluate('()=>document.querySelector("#musicTrack").hidden && document.querySelector("#musicRedMode").hidden'))
            page.goto(url + '/?observe=1')
            wait(page, '()=>document.querySelector("#setup").open')
            page.wait_for_timeout(200)
            check(engine+' 首开0音乐请求', not any('.mp3' in r['url'] for r in requests))
            check(engine+' 观察模式默认静音', page.evaluate('()=>!__waterTest.snapshot().music.enabled'))
            if engine == 'chromium':
                distribution = page.evaluate('''()=>{
                  let seed=20261013, previous=null, repeats=0, counts={};
                  const pool=['c01','c02','c03','c04','c05','c06','c09','c15','orig'];
                  const storage={getItem:()=>previous,setItem:(_,v)=>previous=v};
                  const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
                  for(let i=0;i<1000;i++){
                    const old=previous, next=PoightMusicRandom.pickTrack(pool,random,storage);
                    repeats+=old===next;counts[next]=(counts[next]||0)+1;
                  }
                  const denied={getItem(){throw Error('denied');},setItem(){throw Error('denied');}};
                  const safe=pool.includes(PoightMusicRandom.pickTrack(pool,random,denied));
                  return {seed:20261013,games:1000,counts,repeats,deniedSafe:safe};
                }''')
                observations['lottery'] = distribution
                check('固定种子1000局9首皆被抽到', len(distribution['counts']) == 9, distribution)
                check('1000局0连续重复', distribution['repeats'] == 0, distribution)
                check('localStorage读写拒绝退回纯随机', distribution['deniedSafe'])
            observations[engine] = {}
            for t in tracks:
                page.goto(url + '/?test=1&music='+t['id'])
                check(engine+' '+t['id']+' artwork ready', bool(wait(page,'()=>__waterTest?.snapshot().artReady')))
                page.evaluate('()=>{__waterTest.reset(true);__waterTest.arrange({ai:false});}')
                page.keyboard.press('ArrowRight')
                check(engine+' '+t['id']+' 真实媒体播放', bool(wait(page,'()=>__waterTest.snapshot().music.media?.running')))
                first = page.evaluate('()=>__waterTest.snapshot().music.media.currentTime')
                advanced=bool(wait(page, f'()=>__waterTest.snapshot().music.media?.currentTime>{first+.15}',3))
                state = page.evaluate('()=>__waterTest.snapshot().music')
                check(engine+' '+t['id']+' currentTime前进', advanced, state)
                check(engine+' '+t['id']+' 只在双方资源齐后拉音乐', page.evaluate('()=>mediaAssignments.every(r=>r.artReady)'), page.evaluate('()=>mediaAssignments'))
                check(engine+' '+t['id']+' 无滤波且不随血切换', page.evaluate('''()=>{
                  __waterTest.arrange({ai:false,player:{hp:1}});
                  return __waterTest.snapshot().music.media.running;
                }'''))
                page.keyboard.press('Escape')
                check(engine+' '+t['id']+' 暂停停媒体', bool(wait(page,'()=>__waterTest.snapshot().music.media.paused')))
                frozen = page.evaluate('()=>__waterTest.snapshot().music.media.currentTime')
                page.wait_for_timeout(150)
                check(engine+' '+t['id']+' 暂停不前进', abs(page.evaluate('()=>__waterTest.snapshot().music.media.currentTime')-frozen)<.02)
                page.keyboard.press('Escape')
                check(engine+' '+t['id']+' 恢复同首同进度', bool(wait(page,'()=>__waterTest.snapshot().music.media.running')))
                observations[engine][t['id']] = state['media']
            page.locator('#battleMenuButton').click()
            page.locator('#musicVolume').fill('0')
            check(engine+' 外部媒体0音量', bool(wait(page,'()=>__waterTest.snapshot().music.volume===0 && __waterTest.snapshot().music.media.gain<.01')))
            page.locator('#musicToggle').click()
            check(engine+' 静音停媒体且保存', page.evaluate("()=>!__waterTest.snapshot().music.enabled && __waterTest.snapshot().music.media.paused && !JSON.parse(localStorage.getItem('poight.music.v1')).enabled"))
            page.screenshot(path=out/'截图'/('AUD-'+engine+'-暂停.png'))
            # Real decoded output at the intro -> loop handoff, not just a synthetic timer assertion.
            seam = page.evaluate('''async t=>{
              const ctx=new AudioContext();await ctx.resume();
              const s=new PoightMusicRandom.StreamMusic(t,()=>{},()=>{});
              const until=performance.now()+4000;
              while(!s.ready && performance.now()<until) await new Promise(r=>setTimeout(r,20));
              await s.resume(ctx,.4);
              const capture=ctx.createScriptProcessor(256,2,2), chunks=[];
              s.gains.forEach(g=>g.connect(capture));capture.connect(ctx.destination);
              capture.onaudioprocess=e=>chunks.push({time:e.playbackTime,pcm:[...e.inputBuffer.getChannelData(0)]});
              await new Promise(r=>setTimeout(r,1200));
              const a=s.elements[0];
              await new Promise(r=>{a.onseeked=r;a.currentTime=a.duration-1;});
              await new Promise(r=>setTimeout(r,1500));
              const handoffDeadline=performance.now()+2500;
              while(s.elements[s.active].currentTime<=t.loopStart+.05 && performance.now()<handoffDeadline)
                await new Promise(r=>setTimeout(r,20));
              let run=0,max=0,count=0;
              const boundary=s.seams[0]?.time;
              for(const block of chunks) for(let i=0;i<block.pcm.length;i++){
                const time=block.time+i/ctx.sampleRate;
                if(time<boundary-.12 || time>boundary+.12)continue;
                count++;run=Math.abs(block.pcm[i])<.00001?run+1:0;max=Math.max(max,run);
              }
              const result={seams:s.seams,gapMS:max/ctx.sampleRate*1000,capturedSamples:count,
                nextTime:s.elements[s.active].currentTime,loopStart:t.loopStart,active:s.active,
                nextPaused:s.elements[s.active].paused,ctxState:ctx.state};
              s.dispose();capture.disconnect();await ctx.close();return result;
            }''',tracks[0])
            observations[engine]['introHandoff'] = seam
            check(engine+' 01只放一次intro、后续loopStart', seam['active']==1 and seam['nextTime']>seam['loopStart'], seam)
            check(engine+' 01实际输出接缝空隙≤60ms', seam['capturedSamples']>5000 and seam['gapMS']<=60, seam)
            page.goto(url+'/')
            wait(page,'()=>document.querySelector("#setup").open')
            check(engine+' 正常入口刷新保留静音/音量',
                  page.locator('#musicToggle').text_content()=='音乐：关' and
                  page.locator('#musicVolume').input_value()=='0')
            context.close()
            # Held network proves a timed fallback that cannot late-switch.
            context=browser.new_context()
            held=[]
            context.route('**/bgm-*.mp3',lambda route:held.append(route))
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url+'/?test=1&music=c02')
            wait(page,'()=>__waterTest?.snapshot().artReady')
            begin=time.monotonic()
            page.evaluate('()=>{__waterTest.reset(true);__waterTest.arrange({ai:false});}')
            page.keyboard.press('ArrowRight')
            check(engine+' 3秒原创兜底', bool(wait(page,'()=>__waterTest.snapshot().music.bgm==="orig" && __waterTest.snapshot().music.audible>0',4)))
            elapsed=time.monotonic()-begin
            observations[engine]['fallbackSeconds']=elapsed
            check(engine+' 兜底时限≤3.2秒', 2.8<=elapsed<=3.2,elapsed)
            for route in held:route.continue_()
            page.wait_for_timeout(500)
            check(engine+' 下载迟到不换曲', page.evaluate('()=>__waterTest.snapshot().music.bgm==="orig" && !__waterTest.snapshot().music.media'))
            page.evaluate('()=>{Object.defineProperty(document,"hidden",{configurable:true,value:true});document.dispatchEvent(new Event("visibilitychange"));}')
            check(engine+' 后台暂停', page.evaluate('()=>__waterTest.snapshot().phase==="paused" && !__waterTest.snapshot().music.playing'))
            page.goto(url+'/?demo=1&test=1&fps=60')
            check(engine+' 演示默认静音', bool(wait(page,'()=>__demo?.ready && !__waterTest.snapshot().music.enabled')))
            context.close()
            # Render the live-normalized original green track for independent ffmpeg EBU audit.
            if engine=='chromium':
                context=browser.new_context();page=context.new_page()
                page.goto(url+'/?observe=1&music=off')
                pcm=page.evaluate('''async()=>{
                  const {buffer}=await PoightMusicScore.renderOriginal();
                  const b=new Uint8Array(buffer.getChannelData(0).buffer),parts=[];
                  for(let i=0;i<b.length;i+=16384)parts.push(String.fromCharCode(...b.subarray(i,i+16384)));
                  return btoa(parts.join(''));
                }''')
                import numpy as np
                raw=np.frombuffer(base64.b64decode(pcm),'<f4')
                check('原创归一化渲染无削波', float(np.max(np.abs(raw)))<1)
                with wave.open(str(out/'原创-归一化.wav'),'wb') as f:
                    f.setnchannels(2);f.setsampwidth(2);f.setframerate(44100)
                    f.writeframes(np.repeat((raw*32767).astype('<i2')[:,None],2,axis=1).tobytes())
                context.close()
            browser.close()
    (out/'AUD实播.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2)+'\n')
    loudness=audit(out/'原创-归一化.wav')
    for ident, item in loudness.items():
        check(ident+' ffmpeg实测LUFS偏差≤±1',abs(item['lufs']+16)<=1,item)
        check(ident+' 每首≤1.2MB、≤120秒',item['bytes']<=1_200_000 and item['duration']<=120,item)
    check('9首发布音乐≤8MB',sum(t['bytes'] for t in loudness.values())<=8_000_000,loudness)
    (out/'AUD响度大小.json').write_text(json.dumps(loudness,ensure_ascii=False,indent=2)+'\n')
    check('AUD实播0JS错误',not errors,errors)
