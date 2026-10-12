/* MoveFX: deterministic canvas-only arcade combat drawings. */
(function(root){
'use strict';
root.MoveFX=root.MoveFX||{};
const clamp=v=>Math.max(0,Math.min(1,Number(v)||0));
function poly(c,p,col){c.fillStyle=col;c.beginPath();c.moveTo(p[0],p[1]);for(let i=2;i<p.length;i+=2)c.lineTo(p[i],p[i+1]);c.closePath();c.fill();}
function rect(c,x,y,w,h,col){c.fillStyle=col;c.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h));}
function disk(c,x,y,r,col){c.fillStyle=col;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill();}
function line(c,pts,col,w){c.strokeStyle=col;c.lineWidth=w;c.lineJoin='miter';c.beginPath();c.moveTo(pts[0],pts[1]);for(let i=2;i<pts.length;i+=2)c.lineTo(pts[i],pts[i+1]);c.stroke();}
function seeded(n){let x=Math.sin((Number(n)||0)*78.233+19.19)*43758.5453;return x-Math.floor(x);}
function draw(id,style,label){return function(ctx,s){const u=clamp(s.u), ph=s.phase, src=s.source||{x:200,y:260}, dst=s.target||{x:730,y:260}, hit=!!s.hit, seed=Number(s.seed)||0; let x=src.x,y=src.y, a=0, grow=.55+u*.45, fade=1;
if(ph==='action'){x=src.x+(dst.x-src.x)*u;y=src.y+(dst.y-src.y)*u;} else if(ph==='impact'){x=dst.x;y=dst.y;} else if(ph==='recover'){fade=1-u*.85;}
// All state changes are contained; every motif is anchored to a stable actor/target point.
ctx.save();try{ctx.globalAlpha*=fade;
if(ph==='charge'||ph==='recover') { x=src.x;y=src.y; }
if(style==='agility'||style==='protect'||style==='recover') { x=src.x;y=src.y; }
if(ph==='impact'&&!hit){ctx.restore();return;}
if(style==='fire'){ // 大字爆炎：十字火柱与翻卷尖舌
 if(ph==='charge'||ph==='recover'){disk(ctx,x,y,12+u*29,'#ffb65c');for(let i=0;i<5;i++)poly(ctx,[x-4+i*2,y-5,x-29-i*3,y-26-i*2,x-20-i*2,y-8,x-31-i*2,y+6,x-7,y+4],'#e95a32');}
 else if(ph==='action'){let q=ph==='action'?u:1;const cx=src.x+(dst.x-src.x)*u,cy=y;poly(ctx,[cx-38,cy-8,cx-5,cy-30,cx+24,cy-32,cx+9,cy-13,cx+42,cy-5,cx+9,cy+2,cx+27,cy+27,cx-7,cy+12,cx-28,cy+30,cx-20,cy+7,cx-43,cy+7],'#f36b36');rect(ctx,cx-13,cy-4,34,8,'#ffd879');}
 else {let r=24+u*47;poly(ctx,[x-r,y-10,x-r,y-27,x-8,y-27,x-8,y-r,x+9,y-r,x+9,y-9,x+r,y-9,x+r,y+9,x+9,y+9,x+9,y+r,x-9,y+r,x-9,y+9,x-r,y+9],'#ed6335');rect(ctx,x-r*.62,y-5,r*1.24,10,'#ffd579');}
}else if(style==='surf'){ // 冲浪：层叠浪头、白色泡沫舌
 if(ph==='charge'||ph==='recover'){for(let i=0;i<3;i++){line(ctx,[x-32+i*4,y+18-i*7,x-16,y+12-i*7,x,y+18-i*7,x+17,y+8-i*7,x+34,y+12-i*7],'#65d9f2',4);}disk(ctx,x+18,y-14,6+u*4,'#dcffff');}
 else if(ph==='action'){let q=src.x+(dst.x-src.x)*u;poly(ctx,[q-43,y+17,q-23,y-5,q-5,y-9,q+15,y-30,q+37,y-24,q+20,y-8,q+39,y-1,q+17,y+7,q-5,y+22],'#258bc3');poly(ctx,[q-25,y-3,q-5,y-10,q+14,y-28,q+9,y-9,q+28,y-4,q+5,y+2],'#e7ffff');line(ctx,[q-36,y+21,q-9,y+16,q+14,y+19,q+37,y+13],'#a6f3ff',3);}
 else {poly(ctx,[x-44,y+16,x-29,y-13,x-7,y-2,x+9,y-36,x+39,y-20,x+22,y-2,x+43,y+10,x+16,y+23,x-12,y+21],'#268cc2');poly(ctx,[x-15,y-5,x+8,y-30,x+3,y-7,x+24,y-12,x+10,y+5],'#ecffff');}
}else if(style==='ice'){ // 暴风雪：横向雪针风带、碎冰晶；冰柱坠击：巨型坠晶
 if(id==='iciclecrash'&&(ph==='action'||ph==='impact')){let q=ph==='action'?src.y-80+u*75:y;poly(ctx,[x-15,q-43,x+14,q-43,x+11,q-15,x+22,q-4,x+8,q+25,x-10,q+8,x-21,q-2,x-10,q-17],'#72d9e5');poly(ctx,[x-7,q-31,x+3,q-26,x+1,q+9,x-7,q+17],'#eaffff');if(ph==='impact'&&hit){line(ctx,[x-55,y+28,x-25,y+14,x,y+24,x+25,y+13,x+55,y+24],'#b9faff',4);}}
 else {if(ph==='charge'||ph==='recover'){for(let i=0;i<4;i++)poly(ctx,[x-27+i*15,y-28,x-23+i*15,y-5,x-30+i*15,y+8,x-19+i*15,y+3,x-13+i*15,y+12,x-15+i*15,y-8],'#a8eff2');}
 else {for(let i=0;i<6;i++){let q=src.x+(dst.x-src.x)*u;rect(ctx,q-45+i*17,y-24+(i%3)*17,3,26,'#baf8ff');poly(ctx,[q-30+i*13,y-34+(i%2)*13,q-23+i*13,y-15+(i%2)*13,q-36+i*13,y-7+(i%2)*13],'#efffff');}if(ph==='impact'&&hit)for(let i=0;i<5;i++)poly(ctx,[x-38+i*18,y+26,x-31+i*18,y-5,x-24+i*18,y+26],'#8de5ed');}}
}else if(style==='earthquake'){ // 地震：分层地裂与上拱碎土
 if(ph==='charge'||ph==='recover'){line(ctx,[x-43,y+22,x-24,y+18,x-13,y+25,x,y+17,x+16,y+23,x+34,y+16],'#ad8452',5);}
 else {const q=ph==='action'?src.x+(dst.x-src.x)*u:x;line(ctx,[q-58,y+20,q-37,y+12,q-24,y+24,q-7,y-3,q+4,y+17,q+22,y-8,q+34,y+13,q+56,y+5],'#c7a05f',5);poly(ctx,[q-37,y+14,q-25,y-8,q-15,y+13],'#e7c77e');poly(ctx,[q+22,y+13,q+36,y-13,q+44,y+11],'#9b774b');if(ph==='impact'&&hit)line(ctx,[q-66,y+31,q-32,y+28,q,y+35,q+31,y+27,q+66,y+31],'#f3dc9a',3);}
}else if(style==='earthpower'){ // 大地之力：方尖地柱环列出土
 if(ph==='charge'||ph==='recover'){for(let i=0;i<3;i++)rect(ctx,x-25+i*20,y+12-i*4,8,4+i*2,'#b99b63');}
 else {let q=ph==='action'?src.x+(dst.x-src.x)*u:x;for(let i=0;i<5;i++){let xx=q-45+i*22, h=16+((i*13)%19)+u*5;poly(ctx,[xx-7,y+21,xx-3,y-h,xx+2,y-h-7,xx+8,y+21],'#bd995d');rect(ctx,xx-1,y-h+2,3,Math.max(3,h-2),'#e3c887');}}
}else if(style==='rockslide'){ // 岩崩：不规则下落块与尘土折线
 if(ph==='charge'||ph==='recover'){poly(ctx,[x-27,y+12,x-22,y-9,x-5,y-17,x+8,y-5,x+23,y-3,x+29,y+14,x+5,y+18],'#927d62');}
 else {let q=ph==='action'?src.x+(dst.x-src.x)*u:x;for(let i=0;i<5;i++){let xx=q-38+i*18, yy=y-31+((i*7)%15)+u*8;poly(ctx,[xx-8,yy-5,xx+1,yy-13,xx+11,yy-6,xx+7,yy+6,xx-4,yy+10],'#9d8a6e');line(ctx,[xx-4,yy-3,xx+2,yy-7,xx+7,yy-3],'#d0bd94',2);}if(ph==='impact'&&hit)line(ctx,[q-55,y+21,q-27,y+27,q,y+19,q+30,y+27,q+55,y+20],'#d1b779',4);}
}else if(style==='stoneedge'){ // 尖石攻击：地面扇形尖晶刺出
 if(ph==='charge'||ph==='recover'){poly(ctx,[x-24,y+20,x-15,y+1,x-7,y+16,x+3,y-5,x+10,y+16,x+24,y+7,x+21,y+22],'#a99575');}
 else {let q=ph==='action'?src.x+(dst.x-src.x)*u:x;for(let i=0;i<5;i++){let xx=q-42+i*21, h=22+(i%3)*11;poly(ctx,[xx-9,y+23,xx-3,y-h,xx+2,y-h-8,xx+9,y+23],'#9e8c70');poly(ctx,[xx-2,y-h,xx+2,y-h-8,xx+3,y+4],'#ddd0b1');}}
}else if(style==='hex'){ // 祸不单行：飘浮幽灵暗核，外缘锯齿鬼火
 let xx=(ph==='charge'||ph==='recover')?src.x:(ph==='action'?src.x+(dst.x-src.x)*u:dst.x), yy=y;
 for(let i=0;i<8;i++){let ang=i*Math.PI/4, r=22+(i%3)*4+((ph==='charge')?u*7:0);rect(ctx,xx+Math.cos(ang)*r-4,yy+Math.sin(ang)*r-4,9,9,i%2?'#7061a0':'#ad8bd3');}
 poly(ctx,[xx-20,yy-12,xx-9,yy-22,xx+4,yy-17,xx+20,yy-6,xx+14,yy+1,xx+21,yy+12,xx+3,yy+20,xx-13,yy+13,xx-22,yy+2],'#352a54');disk(ctx,xx,yy,7,'#c5a0e8');if(ph==='impact'&&hit){for(let i=0;i<3;i++)line(ctx,[xx-32+i*20,yy-28,xx-24+i*20,yy-13,xx-30+i*20,yy-7],'#c7a7ef',3);}
}else if(style==='psychic'){ // 精神强念：几何念力压缩透镜与横向折线
 let xx=(ph==='charge'||ph==='recover')?src.x:(ph==='action'?src.x+(dst.x-src.x)*u:dst.x);
 if(ph==='charge'||ph==='recover'){poly(ctx,[xx-28,y,xx-16,y-18,xx,y-25,xx+16,y-18,xx+28,y,xx+16,y+18,xx,y+25,xx-16,y+18],'#d979a5');line(ctx,[xx-20,y,xx,y-11,xx+20,y,xx,y+11,xx-20,y],'#ffe5f0',3);}
 else {poly(ctx,[xx-45,y-5,xx-22,y-13,xx,y-7,xx+23,y-13,xx+46,y-4,xx+21,y+4,xx,y+10,xx-23,y+4],'#df83ad');poly(ctx,[xx-28,y-3,xx,y-8,xx+29,y-2,xx,y+4],'#fff0f6');if(ph==='impact'&&hit)line(ctx,[xx-40,y+24,xx-20,y+17,xx,y+22,xx+20,y+15,xx+40,y+20],'#f8bad0',3);}
}else if(style==='agility'){ // 高速移动：source周围三枚速度折翼，不触及目标
 let r=22+u*23;for(let i=0;i<3;i++){let yy=y-23+i*22;poly(ctx,[x-5,yy,x-22-r*.35,yy-8,x-12-r*.2,yy,x-22-r*.35,yy+8,x+1,yy+3],'#f49db5');}line(ctx,[x-31,y-27,x-43,y-27,x-50,y-17],'#fff0f6',3);line(ctx,[x-31,y+27,x-43,y+27,x-50,y+17],'#fff0f6',3);
}else if(style==='poison'){ // 毒瓦斯：团状毒雾与可读的大泡囊
 let xx=(ph==='charge'||ph==='recover')?src.x:(ph==='action'?src.x+(dst.x-src.x)*u:dst.x);
 for(let i=0;i<5;i++){let bx=xx-22+i*12, by=y+((i%3)-1)*12;disk(ctx,bx,by,10+(i%2)*3,i%2?'#7eaa68':'#9bb66d');}disk(ctx,xx+18,y-17,8,'#d7e889');disk(ctx,xx-16,y-25,5,'#d7e889');if(ph==='impact'&&hit)disk(ctx,xx,y,29,'#6c915d');
}else if(style==='meteor'){ // 流星群：斜掠龙形陨星与碎焰尾
 if(ph==='charge'||ph==='recover'){for(let i=0;i<3;i++)poly(ctx,[x-28+i*16,y-20+i*8,x-18+i*16,y-25+i*8,x-12+i*16,y-8+i*8,x-21+i*16,y-4+i*8],'#9e91e8');}
 else {let q=ph==='action'?src.x+(dst.x-src.x)*u:x, yy=y-25+u*25;poly(ctx,[q-44,yy-17,q-17,yy-13,q-3,yy-24,q+20,yy-10,q+13,yy+11,q-8,yy+18,q-19,yy+5,q-36,yy+6],'#7565c4');poly(ctx,[q-42,yy-9,q-12,yy-6,q+7,yy-10,q-5,yy+2,q-27,yy+1],'#ffd28b');for(let i=0;i<3;i++)rect(ctx,q-48-i*9,yy-4+i*5,8,4,'#e6887c');if(ph==='impact'&&hit)for(let i=0;i<4;i++)poly(ctx,[q-34+i*22,y+27,q-27+i*22,y+8,q-19+i*22,y+27],'#b6a9f4');}
}else if(style==='gleam'){ // 魔法闪耀：四向棱镜切面与菱形星片
 let xx=(ph==='charge'||ph==='recover')?src.x:(ph==='action'?src.x+(dst.x-src.x)*u:dst.x);let r=ph==='charge'?16+u*12:39+u*8;
 poly(ctx,[xx,y-r,xx+8,y-8,xx+r,y,xx+8,y+8,xx,y+r,xx-8,y+8,xx-r,y,xx-8,y-8],'#e9a7d0');poly(ctx,[xx,y-r*.55,xx+5,y-5,xx+r*.55,y,xx+5,y+5,xx,y+r*.55,xx-5,y+5,xx-r*.55,y,xx-5,y-5],'#fff0f9');for(let i=0;i<4;i++)rect(ctx,xx-45+i*29,y-3+(i%2)*17,7,7,'#ffd5ec');
}else if(style==='protect'){ // 守住：source周围方盾龟甲与内层折线
 let r=33;poly(ctx,[x-r,y-20,x-18,y-r,x+18,y-r,x+r,y-20,x+r,y+16,x,y+r,x-r,y+16],'#9e9e7b');poly(ctx,[x-r+7,y-16,x-14,y-r+8,x+14,y-r+8,x+r-7,y-16,x+r-7,y+13,x,y+r-10,x-r+7,y+13],'#e3dfad');line(ctx,[x-18,y-17,x,y-27,x+18,y-17,x+19,y+8,x,y+24,x-19,y+8,x-18,y-17],'#888a74',3);}
else if(style==='recover'){ // 自我再生：源点向上盘旋的叶片与愈合十字
 for(let i=0;i<4;i++){let yy=y-9-i*11;poly(ctx,[x-5,yy,x-24,yy-9,x-18,yy+1,x-4,yy+4],'#75bc83');poly(ctx,[x+5,yy-3,x+22,yy-13,x+17,yy-1,x+4,yy+4],'#9bd58d');}rect(ctx,x-3,y-18,6,25,'#fff3c7');rect(ctx,x-12,y-8,24,6,'#fff3c7');}
ctx.restore();}catch(e){ctx.restore();throw e;}};}
const specs={
 fireblast:['fire','大字爆炎：十字火柱裂开，四边长出翻卷尖舌并露出亮色火芯。'],
 surf:['surf','冲浪：横向浪峰托起白色泡沫舌，沿地面推进并留下分层水线。'],
 blizzard:['ice','暴风雪：多排雪针斜穿风带，命中时迸出宽幅碎晶。'],
 iciclecrash:['ice','冰柱坠击：一根有棱面的长冰柱下坠，着地后弹出短晶刺。'],
 earthquake:['earthquake','地震：地面折线错层开裂，三道土脊向上拱起。'],
 earthpower:['earthpower','大地之力：方形石笋从地面阶梯式突起，侧面带浅色棱线。'],
 rockslide:['rockslide','岩崩：多块不规则岩块错列落下，撞击后扬起折线尘土。'],
 stoneedge:['stoneedge','尖石攻击：扇形排列的长短石刃由下向上穿出地表。'],
 hex:['hex','祸不单行：八枚锯齿鬼火围住不规则暗核，命中再散出幽灵爪痕。'],
 psychic:['psychic','精神强念：菱形念力透镜压扁成横向冲击楔，中心留有亮色折线。'],
 agility:['agility','高速移动：三片折翼速度痕只绕施术者展开，不触碰目标。'],
 poisongas:['poison','毒瓦斯：五团互叠毒云带两枚醒目的空气泡，命中才形成扩散雾核。'],
 dracometeor:['meteor','流星群：斜向龙形陨星拖着分段火尾，命中迸出落星碎片。'],
 dazzlinggleam:['gleam','魔法闪耀：八角棱镜切面向四向绽开，周围飞出大颗菱形星片。'],
 protect:['protect','守住：施术者周围立起龟甲状折面盾，内层描出闭合护盾脊线。'],
 recover:['recover','自我再生：施术者周围叶片螺旋上升，中央浮起清晰愈合十字。']
};
function aerial(ctx,s){let src=s.source||{x:200,y:260},dst=s.target||{x:730,y:260},u=clamp(s.u),ph=s.phase,hit=!!s.hit;let x=ph==='charge'||ph==='recover'?src.x:(ph==='action'?src.x+(dst.x-src.x)*u:dst.x),y=src.y;ctx.save();try{if((ph==='charge'||ph==='recover')){poly(ctx,[x-8,y,x-38,y-25,x-27,y-8,x-50,y-5,x-20,y+2,x-37,y+19,x-6,y+8,x+17,y+20,x+8,y+3,x+31,y-2,x+7,y-8],'#54b9e8');line(ctx,[x-31,y,x-8,y-2,x+10,y],'#efffff',3);}else if(ph==='action'){poly(ctx,[x-4,y-3,x-36,y-31,x-25,y-9,x-52,y-18,x-29,y,x-52,y+18,x-24,y+8,x-34,y+31,x-3,y+4,x+24,y+12,x+7,y+1,x+33,y-9,x+5,y-6],'#39a5da');line(ctx,[x-38,y-27,x-14,y-8,x+3,y,x-20,y+19,x-39,y+30],'#efffff',4);line(ctx,[x-31,y-33,x-4,y-12,x+20,y-2],'#a9eaff',2);}else if(hit){poly(ctx,[x-28,y-17,x-8,y-8,x+23,y-10,x+39,y,x+19,y+7,x-9,y+5,x-31,y+19,x-19,y+2],'#58bce6');line(ctx,[x-25,y-31,x+5,y-4,x+35,y-27],'#efffff',4);line(ctx,[x-31,y+29,x-4,y+4,x+31,y+25],'#a9eaff',3);}ctx.restore();}catch(e){ctx.restore();throw e;}}
for(const id of Object.keys(specs)){const [style,label]=specs[id];root.MoveFX[id]={label,draw:id==='aerialace'?aerial:draw(id,style,label)};}
})(typeof window!=='undefined'?window:globalThis);
