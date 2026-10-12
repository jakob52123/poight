// SPDX-License-Identifier: AGPL-3.0-or-later
// Canvas port of Pokémon Showdown scene/effect semantics. See NOTICE.md.
export const clamp=(n,a=0,b=1)=>Math.min(b,Math.max(a,n));
const lerp=(a,b,t)=>a+(b-a)*t;
export const easing={
 linear:t=>t,accel:t=>t*t,decel:t=>1-(1-t)**2,
 swing:t=>(1-Math.cos(Math.PI*t))/2,
 quadUp:t=>1-(1-t)**2,quadDown:t=>t*t,
 ballisticUp:t=>-3*t*t+4*t,ballisticDown:t=>1-(-3*(1-t)**2+4*(1-t)),
 wave:t=>t+Math.sin(2*Math.PI*t)*.12,
};
function curve(name,t,axis,start,end){
 if(name.startsWith('ballistic')&&!easing[name]){
  if(axis!=='y')return t;
  let up=end.y<start.y;
  if(name.endsWith('Under'))up=!up;
  if(name==='ballistic2Back')up=end.z>0;
  return easing[name.startsWith('ballistic2')?(up?'quadUp':'quadDown'):(up?'ballisticUp':'ballisticDown')](t);
 }
 // Upstream opacity is always linear, even for accel/decel/swing.
 return axis==='opacity'?t:(easing[name]||easing.linear)(t);
}
export class MoveAnimationEngine {
 constructor(data,mapping){this.data=data;this.mapping=mapping;this.images=new Map();this.instances=[];this.shots=[];this.nextId=1;}
 async load(){
  await Promise.all([...new Set(Object.values(this.mapping.effects).map(e=>e.file))].map(async file=>{
   const im=new Image();im.src=file;await im.decode();this.images.set(file,im);
  }));return this;
 }
 cast(id,attacker,defender,{windupMs=null,recoveryMs=null,onImpact=null}={}){
  const move=this.data.moves[id];if(!move)throw Error('招式未转换: '+id);
  const instance=new AnimationInstance(this,move,attacker,defender,windupMs,onImpact,recoveryMs);
  this.instances.push(instance);return instance;
 }
 // Direct API uses the same timeline as JSON. Coordinates here are world pixels.
 scene(attacker,defender,{impactMs=500,windupMs=null,recoveryMs=null}={}){
  const move={id:'direct',impactMs,durationMs:0,events:[]};
  const i=new AnimationInstance(this,move,attacker,defender,windupMs,null,recoveryMs);this.instances.push(i);
  const queues={attacker:0,defender:0};let offset=0;
  const api={instance:i,wait:n=>{offset+=n;},
   showEffect:(fx,start,end,transition='linear',after='')=>{
    const s={scale:1,xscale:null,yscale:null,opacity:1,z:0,...start,time:(start.time||0)+offset};
    const e={...s,...end,time:(end.time??((start.time||0)+500))+offset};
    i.add({type:'effect',fx,start:s,end:e,transition,after,world:true});
   },backgroundEffect:(color,duration,opacity=.3,delay=0)=>i.add({type:'background',color,duration,opacity,time:delay}),
   anim:(role,end,transition='linear')=>{
    const base=i.anchors[role];const before=[...move.events].reverse().find(e=>e.type==='actor'&&e.role===role)?.end||base;
    const s={scale:1,xscale:null,yscale:null,opacity:1,z:0,...before,time:queues[role]};
    const e={scale:1,xscale:null,yscale:null,opacity:1,z:0,...base,...end,time:queues[role]+(end.time??500)};
    queues[role]=e.time;i.add({type:'actor',role,start:s,end:e,transition,world:true});
   },shake:(role='defender',amplitude=5,duration=300)=>i.add({type:'shake',role,amplitude,duration,time:offset}),
   other:name=>{const events=this.data.common[name];if(!events)throw Error('未知 BattleOtherAnims: '+name);for(const e of events)i.add(structuredClone(e));}
  };return api;
 }
 // No integration, velocity or hit detection here: gameplay owns them all.
 createShot(id,attacker,defender,{fx=null,onImpact=null}={}){
  const move=this.data.moves[id];if(!move)throw Error(id);
  const first=move.events.find(e=>e.type==='effect'&&!e.fx.startsWith('@'));
  const shot={id:this.nextId++,moveId:id,attacker,defender,fx:fx||first?.fx||'wisp',position:{x:attacker.x,y:attacker.y},trail:[],hitAt:null,time:0,onImpact};
  shot.update=(position,time)=>{if(shot.hitAt!==null)return;shot.position={...position};shot.time=time;shot.trail.push({...position,time});shot.trail=shot.trail.filter(p=>time-p.time<=160).slice(-16);};
  shot.hit=(position,time)=>{if(shot.hitAt!==null)return;shot.position={...position};shot.hitAt=time;onImpact?.({time,position:{...position}});};
  shot.cancel=()=>{this.shots=this.shots.filter(s=>s!==shot);};
  this.shots.push(shot);return shot;
 }
 drawShots(ctx,time){
  for(const s of this.shots){
   const scale=(s.attacker.height+s.defender.height)/160;
   if(s.hitAt!==null){const p=(time-s.hitAt)/200;if(p>=0&&p<=1)this.drawEffect(ctx,s.fx,{...s.position,z:0,scale:(.4+p*1.8)*scale,xscale:1,yscale:1,opacity:1-p},p*200,s.moveId,1);continue;}
   for(const [j,p] of s.trail.entries())this.drawEffect(ctx,s.fx,{...p,z:0,scale:.25*scale,xscale:1,yscale:1,opacity:.28*(j+1)/s.trail.length},time,s.moveId,1);
   this.drawEffect(ctx,s.fx,{...s.position,z:0,scale:.45*scale,xscale:1,yscale:1,opacity:1},time,s.moveId,1);
  }
 }
 drawEffect(ctx,fx,p,age,moveId,mirror,drawActor=null){
  if(p.opacity<=0||p.scale===0||p.xscale===0||p.yscale===0)return;
  if(fx.startsWith('@')){drawActor?.(fx.slice(1),p,true);return;}
  const key=this.mapping.moveOverrides?.[moveId]?.[fx]||fx,m=this.mapping.effects[key];
  if(!m)throw Error('未映射特效: '+key);
  const image=this.images.get(m.file);if(!image)throw Error('未加载图片: '+m.file);
  const frame=m.frames?.[Math.floor(Math.max(0,age)/(m.frameMs||80))%m.frames.length]||[0,0,image.width,image.height];
  const depth=clamp(1-p.z/1000,.65,1.35),w=m.width*p.scale*p.xscale*depth,h=m.height*p.scale*p.yscale*depth;
  ctx.save();ctx.globalAlpha=clamp(p.opacity);ctx.translate(p.x,p.y);ctx.scale(mirror*(m.flipX?-1:1),1);ctx.imageSmoothingEnabled=false;
  ctx.drawImage(image,...frame,-w/2,-h*(m.pivotY??.5),w,h);ctx.restore();
 }
 clear(){this.instances=[];this.shots=[];}
}
export class AnimationInstance {
 constructor(engine,move,attacker,defender,windupMs,onImpact,recoveryMs=null){
  this.engine=engine;this.move=move;this.actors={attacker,defender};
  this.anchors={attacker:{x:attacker.x,y:attacker.y},defender:{x:defender.x,y:defender.y}};
  this.scale=(attacker.height+defender.height)/160;
  this.mirror=attacker.x>defender.x?-1:1;
  this.impactMs=windupMs===null?move.impactMs:Math.max(0,windupMs);
  this.recoveryMs=recoveryMs;
  this.onImpact=onImpact;this.impacted=false;this.elapsed=0;this.cancelled=false;
 }
 get durationMs(){return this.toRuntime(this.move.durationMs);}
 get blocking(){return !this.cancelled&&this.elapsed<this.impactMs;}
 get done(){return this.cancelled||this.elapsed>this.durationMs;}
 toRuntime(t){const original=this.move.impactMs,tail=Math.max(0,this.move.durationMs-original);return t<=original?(original? t/original*this.impactMs:0):this.impactMs+(this.recoveryMs===null?t-original:tail?(t-original)/tail*this.recoveryMs:0);}
 toSource(t){if(t>=this.impactMs){const tail=Math.max(0,this.move.durationMs-this.move.impactMs);return this.move.impactMs+(this.recoveryMs===null?t-this.impactMs:this.recoveryMs?(t-this.impactMs)/this.recoveryMs*tail:tail);}return this.impactMs?t/this.impactMs*this.move.impactMs:this.move.impactMs;}
 // update fires exactly once even when frames skip over impact. seek/draw never fire gameplay callbacks.
 update(elapsed){this.elapsed=Math.max(0,elapsed);if(!this.cancelled&&!this.impacted&&elapsed>=this.impactMs){this.impacted=true;this.onImpact?.({impactMs:this.impactMs,position:{...this.anchors.defender}});}}
 cancel(){this.cancelled=true;}
 add(event){this.move.events.push(event);this.move.durationMs=Math.max(this.move.durationMs,event.end?event.end.time+(event.after==='fade'?100:event.after==='explode'?200:0):(event.time||0)+event.duration+(event.type==='background'?250:0));}
 coordinate(v,axis){if(typeof v==='number')return v;const a=this.anchors.attacker[axis],d=this.anchors.defender[axis];
  // Unanchored upstream stage effects become centered between the cast-time actors.
  return v.a*a+v.d*d+(Math.abs(v.a)+Math.abs(v.d)<1e-8?(a+d)/2:0)+v.offset*this.scale*(axis==='x'?this.mirror:1);
 }
 point(p,world=false){return {...p,x:world?p.x:this.coordinate(p.x,'x'),y:world?p.y:this.coordinate(p.y,'y')};}
 sample(event,t){
  const start=this.point(event.start,event.world),end=this.point(event.end,event.world);
  const span=end.time-start.time,p=span<=0?1:clamp((t-start.time)/span),out={};
  for(const key of ['x','y','z','opacity'])out[key]=lerp(start[key],end[key],curve(event.transition||'linear',p,key,start,end));
  // Showdown xscale/yscale override scale, they do NOT multiply it.
  for(const key of ['xscale','yscale'])out[key]=lerp(start[key]??start.scale,end[key]??end.scale,curve(event.transition||'linear',p,key,start,end));
  out.scale=event.type==='effect'&&!event.world?this.scale:1;
  if(t>end.time){const n=t-end.time;if(event.after==='fade')out.opacity*=1-clamp(n/100);else if(event.after==='explode'){out.scale*=1+2*clamp(n/200);out.opacity*=1-clamp(n/200);}}
  return out;
 }
 snapshot(elapsed=this.elapsed){
  const t=this.toSource(elapsed),effects=[],backgrounds=[],actors={};
  for(const role of ['attacker','defender'])actors[role]={...this.actors[role],scale:1,xscale:1,yscale:1,opacity:1,z:0};
  for(const e of this.move.events){
   if(e.type==='background'){if(t>=e.time&&t<=e.time+e.duration+250)backgrounds.push({...e,alpha:e.opacity*Math.min(clamp((t-e.time)/250),clamp((e.time+e.duration+250-t)/250))});continue;}
   if(e.type==='shake'){if(t>=e.time&&t<=e.time+e.duration)actors[e.role].x+=Math.sin((t-e.time)*.09)*e.amplitude*(1-(t-e.time)/e.duration);continue;}
   if(t<e.start.time)continue;
   if(e.type==='actor'){
    const p=this.sample(e,Math.min(t,e.end.time));const anchor=this.anchors[e.role];
    // Cosmetic displacement never mutates actor/game position. Live movement is added to cast-time delta.
    actors[e.role]={...actors[e.role],...p,x:this.actors[e.role].x+p.x-anchor.x,y:this.actors[e.role].y+p.y-anchor.y};
   }else if(t<=e.end.time+(e.after==='fade'?100:e.after==='explode'?200:0))effects.push({event:e,position:this.sample(e,t),age:t-e.start.time});
  }
  return {sourceMs:t,elapsed,impactMs:this.impactMs,blocking:elapsed<this.impactMs,actors,effects:effects.sort((a,b)=>b.position.z-a.position.z),backgrounds};
 }
 draw(ctx,elapsed,drawActor){
  if(this.cancelled)return;
  const s=this.snapshot(elapsed);
  for(const b of s.backgrounds){
   const center=this.anchors.defender,radius=this.actors.defender.height*3;
   const colors=(b.color.match(/#[a-f\d]{3,8}/gi)||['#000000']).map(c=>c.length===4?'#'+[...c.slice(1)].map(x=>x+x).join(''):c.slice(0,7));
   ctx.save();ctx.globalAlpha=clamp(b.alpha);ctx.beginPath();ctx.arc(center.x,center.y,radius,0,Math.PI*2);ctx.clip();
   const radial=ctx.createRadialGradient(center.x,center.y,0,center.x,center.y,radius);radial.addColorStop(0,colors.at(-1));radial.addColorStop(.5,colors[0]);radial.addColorStop(1,colors[0]+'00');ctx.fillStyle=radial;ctx.fillRect(center.x-radius,center.y-radius,radius*2,radius*2);ctx.restore();
  }
  const drawFx=f=>this.engine.drawEffect(ctx,f.event.fx,f.position,f.age,this.move.id,this.mirror,drawActor);
  s.effects.filter(f=>f.position.z>0).forEach(drawFx);
  Object.entries(s.actors).sort((a,b)=>b[1].z-a[1].z||a[1].y-b[1].y).forEach(([role,p])=>drawActor(role,p,false));
  s.effects.filter(f=>f.position.z<=0).forEach(drawFx);
  return s;
 }
}
