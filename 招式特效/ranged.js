(function () {
  'use strict';
  window.MoveFX = window.MoveFX || {};
  const TAU = Math.PI * 2;
  const clamp = v => Math.max(0, Math.min(1, Number(v) || 0));
  const hash = (s, i) => { let h = (Number(s) || 0) + i * 374761393; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967295; };
  function poly(c, pts, color) { c.fillStyle = color; c.beginPath(); c.moveTo(pts[0], pts[1]); for (let i=2;i<pts.length;i+=2)c.lineTo(pts[i],pts[i+1]); c.closePath(); c.fill(); }
  function line(c, pts, color, width) { c.strokeStyle=color;c.lineWidth=width;c.lineJoin='miter';c.lineCap='square';c.beginPath();c.moveTo(pts[0],pts[1]);for(let i=2;i<pts.length;i+=2)c.lineTo(pts[i],pts[i+1]);c.stroke(); }
  function ring(c,x,y,r,color,w,start=0,end=TAU){c.strokeStyle=color;c.lineWidth=w;c.beginPath();c.arc(x,y,r,start,end);c.stroke();}
  function star(c,x,y,r1,r2,n,color,rot=0){const p=[];for(let i=0;i<n*2;i++){const a=rot+i*Math.PI/n,r=i%2?r2:r1;p.push(x+Math.cos(a)*r,y+Math.sin(a)*r);}poly(c,p,color);}
  function setup(c,s){c.save();c.globalAlpha=1;c.globalCompositeOperation='source-over';c.translate(s.source.x,s.source.y);}
  function aimed(c,s){c.rotate(Math.atan2(s.target.y-s.source.y,s.target.x-s.source.x));}
  function finish(c){c.restore();}
  function base(ctx,s,kind,col,label,id){let u=clamp(s.u), charge=s.phase==='charge', impact=s.phase==='impact'&&s.hit, recover=s.phase==='recover', action=s.phase==='action';setup(ctx,s);let c=ctx;
    if(s.phase==='impact'&&!s.hit){finish(c);return;}
    if(charge){c.globalAlpha=.35+.55*u;ring(c,0,0,18+22*u,col,3);star(c,0,0,27+10*u,11+4*u,4,'#fff4cf',u*1.4);}
    const distance=Math.hypot(s.target.x-s.source.x,s.target.y-s.source.y);
    if(impact||recover){c.translate(s.target.x-s.source.x,s.target.y-s.source.y);aimed(c,s);c.globalAlpha=1-u;}
    if(action){aimed(c,s);if(s.m.kind==='beam'){c.scale(Math.max(.1,distance/126),1);}else c.translate(distance*u-43,0);c.globalAlpha=1;}
    if(kind==='flame'){
      if(charge){poly(c,[0,-7,-22,-20,-14,-7,-34,0,-14,7,-22,20],col);}
      if(action){poly(c,[8,-10,78,-17,122,-7,105,0,126,6,75,13],col);poly(c,[14,-5,70,-8,96,-2,72,0,102,4,30,6],'#fff1a0');poly(c,[32,-4,49,-15,60,-7,73,-12,69,-2,86,0,62,4,54,15,44,5],'#ff6d32');}
      if(impact){for(let i=0;i<7;i++){let a=i*TAU/7;poly(c,[Math.cos(a)*8,Math.sin(a)*8,Math.cos(a)*52,Math.sin(a)*52,Math.cos(a+.13)*17,Math.sin(a+.13)*17],col);}}
      if(recover)poly(c,[-4,-4,-34,-13,-20,0,-34,10],col);
    }else if(kind==='water'){
      if(charge){for(let i=0;i<3;i++)ring(c,0,0,9+i*9+u*8,i===1?'#d7fbff':col,2);}
      if(action){line(c,[5,0,42,-1,78,1,118,0], '#d8faff',4);line(c,[7,-7,45,-5,92,-6,120,0,89,6,43,5],col,7);for(let i=0;i<5;i++)ring(c,25+i*19,Math.sin(i*2+s.t*9)*3,2.5,'#fff',1);}
      if(impact&&s.hit){for(let i=0;i<6;i++){let a=i*TAU/6;ring(c,Math.cos(a)*19,Math.sin(a)*19,7,'#e2fbff',2);}}
      if(recover){ring(c,0,0,19*(1-u)+3,'#d8faff',2);}
    }else if(kind==='bubble'){
      if(charge){ring(c,0,0,16+u*13,'#e8ffff',3);}
      if(action){for(let i=0;i<6;i++){let x=14+i*17,y=Math.sin(i*2.1+s.t*3)*((i%2)?14:24);ring(c,x,y,6+(i%3)*2,i%2?'#a4efff':'#fff',2);ring(c,x-2,y-2,2,'#fff',1);}}
      if(impact){for(let i=0;i<5;i++)ring(c,15+i*12,Math.sin(i*2)*12,8-i*.5,'#bdf5ff',2);}
      if(recover)ring(c,0,0,20*(1-u)+3,'#a4efff',2);
    }else if(kind==='leaf'){
      if(charge){for(let i=0;i<3;i++){c.save();c.rotate(i*2.1+u);poly(c,[8,-3,33,-8,26,0,33,8,8,3],i?'#6bc777':'#d7ffd2');c.restore();}}
      if(action){for(let i=0;i<4;i++){c.save();c.translate(22+i*25,Math.sin(i*2+s.t*5)*14);c.rotate(s.t*4+i*1.5);poly(c,[-5,0,4,-9,25,0,4,9],'#45a95f');line(c,[-2,0,18,0],'#d9ffc2',1.5);c.restore();}}
      if(impact){star(c,28,0,39,17,6,'#a8ed8a',.2);}
      if(recover){poly(c,[0,0,-35,-16,-24,0,-35,14], '#59b873');}
    }else if(kind==='beam'){
      if(charge){for(let i=0;i<4;i++)line(c,[-4,-18+i*12,-25-u*20,-18+i*12,0,0],col,2);star(c,0,0,18+u*14,7,4,'#fff',Math.PI/4);}
      if(action){let w=kind==='beam'?10:7;poly(c,[0,-w,100,-w/2,126,0,100,w/2,0,w],col);poly(c,[0,-3,92,-2,108,0,92,2,0,3],'#fff');for(let i=0;i<3;i++)line(c,[20,0,49,-20+i*20,76,0],'#f8ffff',1.5);}
      if(impact){star(c,32,0,49,19,8,'#efffff',Math.PI/8);ring(c,32,0,27,'#d8fffa',3);}
      if(recover){line(c,[0,0,-36,0,-52,-8],'#eaffff',3);}
    }else if(kind==='bolt'){
      if(charge){for(let i=0;i<4;i++)line(c,[0,0,-12-i*7,-9+i*6,-23-i*6,-19+i*12],col,3);}
      if(action){poly(c,[0,-5,38,-18,31,-5,78,-12,50,1,91,0,42,14,50,5], '#fff28a');line(c,[0,0,38,-18,31,-5,78,-12],col,3);line(c,[41,4,57,14,72,9],col,3);}
      if(impact){star(c,42,0,45,20,5,'#fff7a8');for(let i=0;i<3;i++)line(c,[35,0,49,-12+i*12,69,-17+i*17],col,3);}
      if(recover)line(c,[0,0,-32,5,-43,-7],col,3);
    }else if(kind==='ice'){
      if(charge){for(let i=0;i<6;i++){let a=i*TAU/6;line(c,[Math.cos(a)*8,Math.sin(a)*8,Math.cos(a)*(20+u*12),Math.sin(a)*(20+u*12)],'#d9ffff',3);}}
      if(action){poly(c,[0,0,34,-10,78,-6,112,0,78,6,34,10], '#81dccc');poly(c,[10,0,41,-3,80,0,41,3],'#f0ffff');for(let i=0;i<3;i++)poly(c,[35+i*23,-5,43+i*23,-16,49+i*23,-5,43+i*23,5],'#cfffff');}
      if(impact){for(let i=0;i<6;i++){let a=i*TAU/6;poly(c,[0,0,Math.cos(a)*45,Math.sin(a)*45,Math.cos(a+.16)*15,Math.sin(a+.16)*15],'#bffbff');}star(c,0,0,18,8,6,'#fff');}
      if(recover)poly(c,[0,0,-35,-12,-24,0,-35,12],'#a5eee3');
    }else if(kind==='crystal'){
      if(charge){poly(c,[-16,0,-4,-15,12,-9,20,0,12,9,-4,15], '#a7a0ff');}
      if(action){poly(c,[5,0,34,-13,59,0,34,13], '#b4a8ff');poly(c,[34,-13,42,0,34,13], '#f7dafa');poly(c,[18,0,34,-7,34,7], '#fff');}
      if(impact){star(c,26,0,44,21,4,'#eedcff',Math.PI/4);for(let i=0;i<4;i++)poly(c,[24,-3,45,-11+i*7,54,-8+i*7,37,2], '#bca9ff');}
      if(recover)poly(c,[0,0,-30,-10,-16,0,-30,10],'#b7a7ff');
    }else if(kind==='shadow'){
      if(charge){for(let i=0;i<6;i++){let a=i*TAU/6;star(c,Math.cos(a)*18,Math.sin(a)*18,5,2,3,'#574278',a);}}
      if(action){poly(c,[2,-14,20,-22,31,-14,48,-18,58,-8,79,-9,88,0,77,12,59,10,48,19,31,14,18,22,2,12,-8,3], '#30233f');poly(c,[12,-6,33,-10,48,-5,66,-6,76,0,61,6,43,4,29,10,12,5], '#a38ad1');for(let i=0;i<4;i++)star(c,25+i*12,Math.sin(i*3)*8,3,1.4,3,'#e7b5ff');}
      if(impact){for(let i=0;i<8;i++){let a=i*TAU/8;poly(c,[0,0,Math.cos(a)*47,Math.sin(a)*47,Math.cos(a+.1)*18,Math.sin(a+.1)*18],i%2?'#433057':'#c49be5');}}
      if(recover)poly(c,[0,0,-35,-16,-24,0,-35,12],'#584372');
    }else if(id==='aerialace'){
      if(charge){poly(c,[-2,-3,-30,-24,-17,-5,-37,0,-17,5,-30,24,-2,3,8,0],'#c8edff');poly(c,[-4,-1,-25,-18,-12,-4,4,0,-12,4,-25,18],'#fff');}
      if(action){let p=clamp(u); c.save();c.translate(94-30*p,Math.sin(p*Math.PI)*-10);c.rotate(Math.PI*.12+Math.sin(p*Math.PI)*.16);poly(c,[-8,-4,-50,-31,-36,-10,-69,0,-36,7,-50,30,-8,4,9,0],'#4c9fd5');poly(c,[-7,-2,-42,-22,-29,-7,3,0,-29,6,-42,22],'#e8fbff');poly(c,[0,-3,41,-12,63,-2,47,0,63,3,41,12],'#8bcff0');c.restore();line(c,[12,0,39,-3,62,0,47,3,26,1],'#fff',2);}
      if(impact){poly(c,[0,0,53,-39,38,-8,68,0,38,8,53,39],'#e9fbff');poly(c,[8,0,40,-16,31,-3,50,0,31,3],'#66b8e3');}
      if(recover){poly(c,[0,0,-38,-19,-24,0,-38,18],'#a8dff5');ring(c,-14,0,16*(1-u), '#e8fbff',2);}
    }else if(kind==='air'){
      if(charge){poly(c,[0,0,-30,-24,-15,-8,16,0,-15,8,-30,24], '#dff8ff');}
      if(action){poly(c,[5,-7,53,-20,34,-4,86,-11,56,1,87,6,37,7,55,19], '#d9f4ff');line(c,[10,0,72,-2,99,0], '#fff',2);}
      if(impact){poly(c,[0,0,53,-32,30,-3,61,0,27,5,47,31], '#e9fbff');}
      if(recover)line(c,[0,0,-39,-18,-25,0,-39,18],'#a4d8ee',4);
    }else if(kind==='orb'){
      if(charge){ring(c,0,0,14+u*13,col,4);star(c,0,0,15+u*8,6,4,'#fff');}
      if(action){c.fillStyle=col;c.beginPath();c.arc(43,0,15,0,TAU);c.fill();ring(c,43,0,21,'#fff1d8',2);for(let i=0;i<4;i++)star(c,10+i*17,Math.sin(i*2+s.t*3)*8,4,2,4,'#fff');}
      if(impact){star(c,43,0,39,17,8,'#fff2d4');ring(c,43,0,24,col,4);}
      if(recover){ring(c,0,0,17*(1-u)+2,col,2);}
    }else if(kind==='poison'){
      if(charge){for(let i=0;i<3;i++)ring(c,-4+i*6,0,7+i*5,'#d0b0e2',2);}
      if(action){for(let i=0;i<5;i++){let x=14+i*17,y=Math.sin(i*2+s.t*2)*12;poly(c,[x,y-10,x+4,y-3,x+13,y,x+4,y+3,x,y+10,x-4,y+3,x-12,y,x-4,y-3], '#9c74b8');}}
      if(impact){for(let i=0;i<6;i++){let a=i*TAU/6;poly(c,[Math.cos(a)*7,Math.sin(a)*7,Math.cos(a)*38,Math.sin(a)*38,Math.cos(a+.2)*15,Math.sin(a+.2)*15],'#c89de2');}}
      if(recover)ring(c,0,0,18*(1-u)+3,'#b890ce',2);
    }
    if(impact&&s.hit){ctx.globalAlpha=1-u;ring(ctx,0,0,8+u*30,'#fff3c5',2);star(ctx,0,0,(10+u*18)*(1-u),4,4,'#fff');}
    finish(ctx);
  }
  const specs={
    flamethrower:['喷射火焰','flame','#ff8b3d'],watergun:['水枪','water','#42bde8'],bubble:['泡沫','bubble','#9deaff'],hydropump:['水炮','beam','#42bde8'],razorleaf:['飞叶快刀','leaf','#58bb67'],solarbeam:['日光束','beam','#e6c84f'],thunderbolt:['十万伏特','bolt','#ffe45b'],icebeam:['冰冻光束','ice','#a5eee3'],iceshard:['冰砾','crystal','#a5eee3'],airslash:['空气斩','air','#bde8f4'],aurasphere:['波导弹','orb','#f08e59'],powergem:['力量宝石','crystal','#cf87c7'],shadowball:['暗影球','shadow','#705c9c'],psychocut:['精神利刃','crystal','#f1a2c2'],flashcannon:['加农光炮','beam','#bed7d1'],poisonsting:['毒针','poison','#ae84c4'],sludgebomb:['污泥炸弹','shadow','#967044'],signalbeam:['信号光束','beam','#b7d768'],dragonbreath:['龙息','flame','#9d8bdf'],darkpulse:['恶之波动','shadow','#887763'],moonblast:['月亮之力','orb','#e8bddd'],hyperbeam:['破坏光线','beam','#f4efc8']
  };
  const shapes={flame:'尖舌翻卷火焰',water:'收束水线',bubble:'扇形空气泡',leaf:'旋转叶刃',beam:'贯穿光束',bolt:'分叉折线闪电',ice:'棱晶冰束',crystal:'切面晶体飞片',air:'折返鸟翼切线',orb:'带轨道纹的能量球',shadow:'不规则暗核与脉冲边缘',poison:'针刺与滴形毒芒'};
  Object.keys(specs).forEach(function(id){
    const item=specs[id], name=item[0], kind=item[1], color=item[2];
    window.MoveFX[id]={label:name+'：以清晰的街机几何轮廓表现'+(shapes[kind]||'招式轨迹')+'。',draw:function(ctx,s){base(ctx,s,kind,color,name,id);}};
  });
})();
