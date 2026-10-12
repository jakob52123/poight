'use strict';
const $=id=>document.getElementById(id),ctx=$('view').getContext('2d'),moves=LAB.moves,ids=Object.keys(moves),keys=new Set(),charCache=new Map(),fxCache=new Map();
const names={shot:'飞行弹道',stream:'连续喷射',melee:'贴身动作',rush:'身体冲刺',wave:'向前扩散',fall:'固定落点',ground:'地面 / 局部',selfarea:'周身范围',support:'作用自身'};
let current='fireblast',t=0,playing=false,speed=1,mode='front',enemyShift=0,category='all',filtered=[...ids],ready=false,last=performance.now(),renderError=null,requestToken=0;
const start={x:348,y:260};
function text(id,value){if($(id).textContent!==value)$(id).textContent=value;}
function pressed(id,on){$(id).setAttribute('aria-pressed',String(on));}
function setPlaying(on){playing=on;text('play',on?'暂停':'播放');}
function clamp(x,a=0,b=1){return Math.max(a,Math.min(b,x));}
function image(src){const im=new Image(),promise=new Promise((resolve,reject)=>{im.onload=()=>resolve(im);im.onerror=()=>reject(Error('图片解码失败'));});im.src=src;return{im,promise};}
const ground=image(SCENE.ground),objects=image(SCENE.objects);
function loadCharacter(id){if(charCache.has(id))return charCache.get(id);const entry={images:{},promise:null};charCache.set(id,entry);entry.promise=Promise.all(Object.entries(SCENE.characters[id].art).map(async([role,a])=>{const x=image(a.src);entry.images[role]=x.im;await x.promise;}));return entry;}
function loadFX(id){if(!fxCache.has(id))fxCache.set(id,image(moves[id].src));return fxCache.get(id);}
function total(m=moves[current]){return m.windup+m.duration+m.hold+m.fade+m.rest;}
function frameAt(a,age,loop){let time=loop?Math.max(0,age)%a.totalDuration:clamp(age,0,Math.max(0,a.totalDuration-.00001));for(let i=0;i<a.frames;i++){if(time<a.durations[i])return i;time-=a.durations[i];}return a.frames-1;}
function group(m){return['shot','stream','wave'].includes(m.mode)?'ranged':['rush','melee'].includes(m.mode)?'contact':m.mode==='support'?'support':'field';}
function actor(id,pos,target,s){const c=SCENE.characters[id];let role='idle',age=t,loop=true,frame=null;
 if(target&&s.contact){role='hurt';age=c.art.hurt.totalDuration*.45;loop=false;}
 if(!target){
  if(s.phase==='charge'){role=['melee','rush'].includes(s.m.mode)?'melee':'shoot';const a=c.art[role];age=(a.hitTime??a.totalDuration*.45)*s.u;loop=false;}
  else if(s.phase==='action'){
   if(s.m.mode==='rush'){role='dash';age=s.elapsed;loop=true;}
   else if(s.m.mode==='melee'){role='melee';const a=c.art[role],hit=a.hitTime??a.totalDuration*.45;age=hit+(a.totalDuration-hit)*clamp(s.elapsed/s.m.duration);loop=false;}
   else if(s.m.mode==='stream'){role='shoot';frame=s.m.poseFrame??c.art.shoot.hitFrame??Math.floor(c.art.shoot.frames/2);}
   else if(s.elapsed<.32){role='shoot';const a=c.art[role];age=(a.hitTime??a.totalDuration*.45)+(a.totalDuration-(a.hitTime??a.totalDuration*.45))*clamp(s.elapsed/.32);loop=false;}
  }
 }
 const a=c.art[role];frame=clamp(frame??frameAt(a,age,loop),0,a.frames-1);const row=a.rows===1?0:target?2:6,body=a.bodyOffsets?.[row]?.[frame]||[0,0],scale=c.meta.scale,foot=pos.y+(c.meta.flightHeight||26),x=pos.x-(a.anchorX+body[0])*scale,y=c.meta.flightHeight?pos.y-(a.anchorY+body[1])*scale:foot-a.anchorY*scale;
 const point=(p)=>({x:x+p[0]*scale,y:y+p[1]*scale});let front=point(a.frontPoints[frame]),center=point(a.centerPoints[frame]),bottom=point(a.bottomPoints[frame]);
 if(target){center={x:pos.x,y:pos.y-4};front={x:pos.x-20,y:pos.y-4};bottom={x:pos.x,y:foot};}
 return{id,c,role,frame,row,scale,x,y,pos,foot,front,center,bottom,point,alpha:!target&&s.m.id==='phantomforce'&&s.phase==='action'?.25:1};
}
function releasePoint(m){const c=SCENE.characters[m.caster],a=c.art.shoot,frame=clamp(m.poseFrame??a.hitFrame??Math.floor(a.frames/2),0,a.frames-1),body=a.bodyOffsets?.[6]?.[frame]||[0,0],scale=c.meta.scale;let p=m.emitLocal||a.frontPoints[frame];if(m.emit==='top')p=[a.centerPoints[frame][0],a.centerPoints[frame][1]-12];
 return{x:start.x+(p[0]-a.anchorX-body[0])*scale,y:c.meta.flightHeight?start.y+(p[1]-a.anchorY-body[1])*scale:start.y+26+(p[1]-a.anchorY)*scale};}
function snapshot(){const m=moves[current],elapsed=t-m.windup,phase=t<m.windup?'charge':elapsed<m.duration+m.hold?'action':'recover',u=phase==='charge'?t/m.windup:phase==='action'?clamp(elapsed/(m.duration+m.hold)):clamp((elapsed-m.duration-m.hold)/(m.fade+m.rest)),live=elapsed>=0&&elapsed<m.duration+m.hold+m.fade,alpha=elapsed>m.duration+m.hold?clamp(1-(elapsed-m.duration-m.hold)/m.fade):1,p=clamp(elapsed/m.duration),release=releasePoint(m),source={...start};
 if(m.mode==='rush')source.x+=m.reach*p;
 const defaultX=m.mode==='melee'?start.x+54:m.mode==='support'?start.x+158:['selfarea'].includes(m.mode)?start.x+55:release.x+Math.max(72,m.reach*.78);
 const target={x:defaultX+(mode==='far'?m.reach+140:0),y:260+enemyShift+(mode==='dodge'?-110:0)},spot={x:defaultX,y:260},front=clamp(elapsed*m.speed,0,m.reach),effectPosition={x:release.x+front,y:release.y};
 const s={m,current,t,elapsed,phase,u,p,live,alpha,source,target,spot,front,release,effectPosition,contact:false,playing,speed,mode,ready,total:total(),formalCollision:false};
 s.player=actor(m.caster,source,false,s);const enemyCenter={x:target.x,y:target.y-4};let reachContact=false;
 if(live&&alpha>.1){
  if(m.mode==='stream')reachContact=front>=target.x-18-release.x&&target.x>=release.x&&Math.abs(release.y-enemyCenter.y)<25;
  else if(m.mode==='shot')reachContact=Math.abs(effectPosition.x-enemyCenter.x)<20+Math.min(m.width,m.height)*.32&&Math.abs(effectPosition.y-enemyCenter.y)<22+Math.min(m.width,m.height)*.32;
  else if(m.mode==='wave'){effectPosition.y=287;reachContact=Math.abs(effectPosition.x-enemyCenter.x)<m.width*.36+18&&Math.abs(target.y-260)<45;}
  else if(m.mode==='rush')reachContact=Math.abs(s.player.center.x-enemyCenter.x)<40&&Math.abs(s.player.center.y-enemyCenter.y)<48;
  else if(m.mode==='melee')reachContact=Math.abs(s.player.front.x-enemyCenter.x)<Math.max(22,m.reach*.65)&&Math.abs(s.player.front.y-enemyCenter.y)<37&&elapsed<m.duration;
  else if(['ground','fall'].includes(m.mode))reachContact=elapsed>m.duration*.35&&Math.abs(spot.x-target.x)<m.width*.4+12&&Math.abs(target.y-spot.y)<32;
  else if(m.mode==='selfarea')reachContact=elapsed>m.duration*.2&&Math.hypot(target.x-source.x,(target.y-source.y)*1.3)<Math.max(55,m.reach);
 }
 s.contact=reachContact;s.enemy=actor(SCENE.target,target,true,s);return s;}
function background(){ctx.fillStyle='#73cda4';ctx.fillRect(0,0,960,540);if(ground.im.complete&&ground.im.naturalWidth)ctx.drawImage(ground.im,0,0,SCENE.environment.world.width,SCENE.environment.world.height);}
function shadow(p,target){ctx.save();ctx.fillStyle='#102e3d50';ctx.beginPath();ctx.ellipse(p.pos.x,p.foot,p.c.meta.flightHeight?17:23,p.c.meta.flightHeight?6:8,0,0,Math.PI*2);ctx.fill();ctx.strokeStyle=target?'#dd915b':'#53bcf0';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(p.pos.x,p.foot+1,27,11,0,0,Math.PI*2);ctx.stroke();ctx.restore();}
function drawActor(p){const im=loadCharacter(p.id).images[p.role],a=p.c.art[p.role];if(!im?.complete||!im.naturalWidth)return;ctx.save();ctx.globalAlpha=p.alpha;ctx.drawImage(im,p.frame*a.frameWidth,p.row*a.frameHeight,a.frameWidth,a.frameHeight,Math.round(p.x),Math.round(p.y),a.frameWidth*p.scale,a.frameHeight*p.scale);ctx.restore();}
function labels(p,target,shift=0){const name=(target?'对手 · ':'演示 · ')+p.c.meta.name;ctx.save();ctx.font='bold 12px system-ui';ctx.textAlign='center';const width=ctx.measureText(name).width+14,y=p.pos.y-58,x=p.pos.x+shift;ctx.fillStyle='#102638de';ctx.fillRect(Math.round(x-width/2),y-12,Math.round(width),20);ctx.fillStyle=target?'#ffcc91':'#b5ecff';ctx.fillText(name,x,y+2);ctx.restore();}
function stamp(m,pos,frame,alpha=1,scaleOverride=null,clip=null){const im=loadFX(m.id).im;if(!ready||!im.complete||!im.naturalWidth||alpha<=0)return;const sc=scaleOverride??Math.min(m.width/m.fw,m.height/m.fh),sourceWidth=clip===null?m.fw:clamp(clip/sc,0,m.fw);if(sourceWidth<=0)return;ctx.save();ctx.globalAlpha=alpha;ctx.drawImage(im,0,frame*m.fh,sourceWidth,m.fh,Math.round(pos.x-m.ax*sc),Math.round(pos.y-m.ay*sc),sourceWidth*sc,m.fh*sc);ctx.restore();}
function effect(s,layer){const m=s.m,grounded=['ground','fall','selfarea'].includes(m.mode)&&m.anchor==='bottom';if(grounded!==(layer==='under'))return;
 if(!s.live||s.alpha<=0)return;let f=['shot','stream','rush','wave'].includes(m.mode)?Math.floor(Math.max(0,s.elapsed)*7)%4:Math.min(3,Math.floor(s.p*4));
 if(m.mode==='stream'){const scale=m.reach/(m.fw-m.ax),length=s.contact?Math.min(s.front,s.target.x-18-s.release.x):s.front;stamp(m,s.release,f,s.alpha,scale,length+m.ax*scale);return;}
 if(m.mode==='shot'){stamp(m,s.effectPosition,f,s.alpha);return;}
 if(m.mode==='wave'){const pos={...s.effectPosition};if(m.anchor!=='bottom')pos.y=260;stamp(m,pos,f,s.alpha);return;}
 if(m.mode==='rush'){let pos=s.player.center;if(m.anchor==='right')pos={x:s.player.center.x-9,y:s.player.center.y};stamp(m,pos,f,s.alpha);return;}
 if(m.mode==='melee'){
  let pos={...s.player.front};
  if(m.id==='vinewhip')pos={x:s.player.center.x+4,y:s.player.center.y-3};
  if(m.id==='irontail')pos={x:s.player.center.x-12,y:s.player.center.y+9};
  // Attach to the current native limb edge; do not slide the actor toward the opponent.
  stamp(m,pos,f,s.alpha);return;
 }
 if(m.mode==='support'||m.mode==='selfarea'){const pos=m.anchor==='bottom'?{x:s.source.x,y:s.player.foot}:s.player.center;stamp(m,pos,f,s.alpha);return;}
 const pos={x:s.spot.x,y:m.anchor==='bottom'?s.spot.y+26:s.spot.y-4};stamp(m,pos,f,s.alpha);
}
function scene(s){background();effect(s,'under');shadow(s.player,false);shadow(s.enemy,true);const layers=[{z:s.player.foot,p:s.player},{z:s.enemy.foot,p:s.enemy}];for(const o of SCENE.environment.sprites)if(o.x<960&&o.y<540&&o.x+o.w*o.scale>0&&o.y+o.h*o.scale>0)layers.push({z:o.z,o});layers.sort((a,b)=>a.z-b.z);for(const q of layers){if(q.p)drawActor(q.p);else if(objects.im.complete&&objects.im.naturalWidth){const o=q.o;ctx.drawImage(objects.im,o.sx,o.sy,o.w,o.h,o.x,o.y,o.w*o.scale,o.h*o.scale);}}effect(s,'over');const near=Math.abs(s.player.pos.x-s.enemy.pos.x)<125;labels(s.player,false,near?-42:0);labels(s.enemy,true,near?42:0);}
function render(){ctx.setTransform(2,0,0,2,0,0);ctx.imageSmoothingEnabled=false;try{const s=snapshot();scene(s);text('phase',!ready?'素材载入中':s.phase==='charge'?'01 / 看清起手':s.phase==='action'?'02 / '+names[s.m.mode]:'03 / 收招');text('phaseHint',`起手 ${s.m.windup.toFixed(2)}秒 · 动作 ${s.m.duration.toFixed(2)}秒 · 方向 / 落点固定`);text('contact',s.m.mode==='support'?'辅助：作用自身':s.contact?'演示接触到对手':s.phase==='charge'?'准备出招':s.live?'移动 / 释放中 · 未接触':'等待下一次');text('status',`${t.toFixed(2)} / ${s.total.toFixed(2)}秒 · ${speed===1?'正常速度':'半速'} · ${s.m.reach?`试演范围 ${s.m.reach}px`:'自身技能'} · ${playing?'循环播放':'暂停'}`);$('time').value=t;}catch(e){fail(e);}}
function fail(e){renderError=String(e);setPlaying(false);text('status','预览错误：'+e.message);console.error(e);}
async function select(id){if(!moves[id])throw Error('Unknown move');const token=++requestToken;current=id;t=0;enemyShift=0;mode='front';ready=false;setPlaying(false);$('notePanel').hidden=true;const m=moves[id];text('number',`GENERATED ${String(ids.indexOf(id)+1).padStart(2,'0')} / ${ids.length}`);text('moveName',m.name);text('typeBadge',LAB.types[m.type][0]+' · '+names[m.mode]);text('description',m.attachment);$('time').max=total();$('original').href=m.original.split('/').map(encodeURIComponent).join('/');
 const notes=[];if(m.reviewNote)notes.push(m.reviewNote);if(m.needsEdgeReview)notes.push('这张原图带底色，已本地提取透明蒙版；浅色边缘是待验收项。');if(m.learnsetWarning)notes.push('暂借该角色演示形状，尚未确认首发50中谁能学会；不会据此添加配招。');text('caution',notes.join(' '));$('caution').hidden=!notes.length;
 for(const x of ['front','dodge','far']){pressed(x,x==='front');$(x).disabled=m.mode==='support';}for(const b of $('list').children)if(b.dataset.move)b.setAttribute('aria-pressed',String(b.dataset.move===id));
 await Promise.all([ground.promise,objects.promise,loadCharacter(m.caster).promise,loadCharacter(SCENE.target).promise,loadFX(id).promise]);if(token!==requestToken)return;ready=true;render();setPlaying(true);for(const key of charCache.keys())if(charCache.size>6&&key!==m.caster&&key!==SCENE.target)charCache.delete(key);
}
function drawList(){const q=$('search').value.trim().toLowerCase();filtered=ids.filter(id=>(category==='all'||group(moves[id])===category)&&(!q||(moves[id].name+LAB.types[moves[id].type][0]+id).toLowerCase().includes(q)));$('list').replaceChildren();for(const id of filtered){const m=moves[id],b=document.createElement('button');b.className='move';b.dataset.move=id;b.style.setProperty('--type-color',m.color);b.setAttribute('aria-pressed',String(id===current));const num=document.createElement('span'),body=document.createElement('span'),name=document.createElement('b'),sub=document.createElement('small');num.className='num';num.textContent=String(ids.indexOf(id)+1).padStart(2,'0');body.className='body';name.textContent=m.name;sub.textContent=LAB.types[m.type][0]+' / '+names[m.mode];body.append(name,sub);b.append(num,body);b.onclick=()=>{select(id).catch(fail);$('sidebar').classList.remove('open');};$('list').append(b);}text('count',`${filtered.length} / 57招 · 生图原件已齐`);}
for(const [id,label]of Object.entries({all:'全部',ranged:'远程',contact:'近身 / 冲刺',field:'范围',support:'辅助'})){const b=document.createElement('button');b.textContent=label;b.dataset.group=id;b.setAttribute('aria-pressed',String(id==='all'));b.onclick=()=>{category=id;for(const x of $('categories').children)x.setAttribute('aria-pressed',String(x===b));drawList();};$('categories').append(b);}
function navigate(n){const list=filtered.length?filtered:ids,index=list.indexOf(current);select(list[(index+n+list.length)%list.length]).catch(fail);$('list').querySelector(`[data-move="${current}"]`)?.scrollIntoView({block:'nearest'});}
function restart(){t=0;setPlaying(true);render();}
$('search').oninput=drawList;$('previous').onclick=()=>navigate(-1);$('next').onclick=()=>navigate(1);$('play').onclick=()=>setPlaying(!playing);$('restart').onclick=restart;$('normal').onclick=()=>{speed=1;pressed('normal',true);pressed('slow',false);};$('slow').onclick=()=>{speed=.5;pressed('normal',false);pressed('slow',true);};$('time').oninput=()=>{t=Number($('time').value);setPlaying(false);render();};
for(const id of ['front','dodge','far'])$(id).onclick=()=>{mode=id;enemyShift=0;for(const x of ['front','dodge','far'])pressed(x,x===id);restart();};$('mobileList').onclick=()=>$('sidebar').classList.toggle('open');$('closeList').onclick=()=>$('sidebar').classList.remove('open');
let notes={};try{notes=JSON.parse(localStorage.getItem('pocket-generated-fx-notes-v1')||'{}');}catch{}
function openNote(){setPlaying(false);$('notePanel').hidden=false;text('noteTitle',moves[current].name+' · '+t.toFixed(2)+'秒');$('noteText').value=notes[current]?.text||'';$('noteText').dataset.move=current;$('noteText').dataset.time=String(t);$('noteText').focus();text('noteState','');}
$('note').onclick=openNote;$('closeNote').onclick=()=>$('notePanel').hidden=true;$('saveNote').onclick=()=>{const id=$('noteText').dataset.move;notes[id]={move:moves[id].name,text:$('noteText').value,time:Number($('noteText').dataset.time)};try{localStorage.setItem('pocket-generated-fx-notes-v1',JSON.stringify(notes));text('noteState',' 已保存在本机');}catch{text('noteState',' 保存不可用，请导出意见');}};
$('exportNotes').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(notes,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='57招生图-审阅意见.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.addEventListener('keydown',e=>{if(/INPUT|TEXTAREA/.test(e.target.tagName)||e.ctrlKey||e.metaKey||e.altKey)return;if(e.code==='Escape'){$('sidebar').classList.remove('open');$('notePanel').hidden=true;}if(e.code==='Space'){e.preventDefault();openNote();}if(['ArrowUp','ArrowDown'].includes(e.code)){e.preventDefault();keys.add(e.code);}if(e.code==='ArrowLeft'){e.preventDefault();navigate(-1);}if(e.code==='ArrowRight'){e.preventDefault();navigate(1);}});document.addEventListener('keyup',e=>keys.delete(e.code));window.addEventListener('blur',()=>keys.clear());document.addEventListener('visibilitychange',()=>{if(document.hidden){keys.clear();setPlaying(false);}});
function loop(now){const dt=Math.min(.08,(now-last)/1000);last=now;if(keys.size)enemyShift=clamp(enemyShift+((keys.has('ArrowDown')?1:0)-(keys.has('ArrowUp')?1:0))*110*dt,-135,135);if(playing&&ready)t=(t+dt*speed)%total();render();requestAnimationFrame(loop);}
window.__generatedLab={ids,moves,select,snapshot,seek(v){t=clamp(Number(v),0,total());setPlaying(false);render();},setMode(v){if(!['front','dodge','far'].includes(v))throw Error('Invalid mode');mode=v;enemyShift=0;render();},moveTarget(dy){enemyShift=dy;render();},error:()=>renderError,ready:()=>ready,artOnly:true};
drawList();select(current).catch(fail);requestAnimationFrame(loop);
