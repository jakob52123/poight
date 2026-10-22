/* Phone gamepad transport. Simulation remains in PoightMobile's game API. */
(() => {
  'use strict';
  const phone = location.pathname.endsWith('/手机手柄.html') || decodeURI(location.pathname).endsWith('/手机手柄.html');
  const $ = id => document.getElementById(id);
  let socket, retry = 400, stopped = false, timer, room = '', token = '', joined = false;
  let vector = {x:0,y:0}, seq = 0, input, lastReceive = 0;
  const status = text => { const el = $(phone ? 'padStatus' : 'remoteStatus'); if (el) el.textContent = text; };
  function send(obj) { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(obj)); }
  function connect() {
    clearTimeout(timer);
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/relay`);
    socket = ws;
    socket.onopen = () => {
      if (socket !== ws) return;
      lastReceive = Date.now();
      send({role:phone ? 'phone' : 'host',room,token});
      status('连接中…');
    };
    socket.onmessage = event => {
      if (socket !== ws) return;
      lastReceive = Date.now();
      const msg = JSON.parse(event.data);
      if (msg.type === 'room') {
        room = msg.room; token = msg.token; retry = 400;
        $('remoteCode').textContent = room;
        const url = new URL('/手机手柄.html', location.href); url.searchParams.set('room', room);
        $('remoteLink').href = url.href; $('remoteLink').textContent = url.href;
        const qr = qrcode(0,'M'); qr.addData(url.href); qr.make();
        $('remoteQR').innerHTML = qr.createSvgTag({cellSize:3,margin:12,scalable:true});
        status(msg.connected ? '手柄已连接' : '等待手机连接');
      } else if (msg.type === 'joined') {
        joined = true; token = msg.token; retry = 400; status('已连接 · 横屏操作');
      } else if (msg.type === 'status') {
        status(msg.connected ? (phone ? '已连接 · 横屏操作' : '手柄已连接') : (phone ? '电脑已断开，等待恢复' : '手柄已断开'));
        if (!msg.connected) input?.remoteClear();
      } else if (msg.type === 'input') {
        input?.remoteInput(msg);
        // Instrumentation measures receive time without changing game state.
        window.poightRemoteLast = {seq:msg.seq,at:performance.now(),action:msg.action};
        if (msg.action) window.poightRemoteLastAction = window.poightRemoteLast;
      } else if (msg.type === 'error') {
        stopped = true; status(msg.message + '；请检查房间码后重新连接');
      }
    };
    socket.onclose = () => {
      if (socket !== ws) return;
      joined = false; vector = {x:0,y:0}; input?.remoteClear();
      if (stopped) return;
      status('连接断开，自动重连…');
      timer = setTimeout(connect, retry + Math.random()*150); retry = Math.min(retry*2,8000);
    };
    socket.onerror = () => ws.close();
  }
  function packet(action) { if (joined) send({type:'input',...vector,action,seq:++seq}); }
  if (phone) {
    room = new URLSearchParams(location.search).get('room')?.toUpperCase() || '';
    $('roomCode').value = room;
    $('joinRoom').onsubmit = e => {
      e.preventDefault(); stopped = true; clearTimeout(timer); socket?.close();
      room = $('roomCode').value.trim().toUpperCase(); token = ''; stopped = false; connect();
    };
    const stick = $('padStick'), knob = $('padKnob'); let pointer = null;
    let moveFrame = null, lastMoveSent = -Infinity;
    const flushMove = now => {
      // Cap high-refresh displays too, rather than sending at 120+ Hz.
      if (now - lastMoveSent < 16) { moveFrame = requestAnimationFrame(flushMove); return; }
      moveFrame = null; lastMoveSent = now; packet();
    };
    const move = e => {
      if (pointer !== e.pointerId) return;
      const r = stick.getBoundingClientRect(), dx = e.clientX-r.x-r.width/2, dy=e.clientY-r.y-r.height/2;
      const length = Math.hypot(dx,dy), radius = r.width*.34, gain = Math.min(1,length/radius);
      vector = {x:length ? dx/length*gain:0,y:length ? dy/length*gain:0};
      knob.style.transform=`translate(${vector.x*radius}px,${vector.y*radius}px)`;
      if (moveFrame === null) moveFrame = requestAnimationFrame(flushMove);
    };
    const clear = () => {
      cancelAnimationFrame(moveFrame); moveFrame = null;
      pointer=null; vector={x:0,y:0};knob.style.transform='none';packet();
    };
    stick.onpointerdown = e => {e.preventDefault(); pointer=e.pointerId;stick.setPointerCapture(pointer); move(e);};
    stick.onpointermove = move;
    stick.onpointerup = clear; stick.onpointercancel = clear; stick.onlostpointercapture = clear;
    for (const button of document.querySelectorAll('[data-action]')) {
      button.onpointerdown = e => {e.preventDefault();packet(button.dataset.action);};
      button.onclick = e => {if (!e.detail) packet(button.dataset.action);};
    }
    window.addEventListener('blur',clear);
    document.addEventListener('visibilitychange',clear);
    // Refresh held state; desktop watchdog releases movement after 700 ms silence.
    setInterval(() => {
      if (!document.hidden && moveFrame === null && performance.now() - lastMoveSent >= 50) packet();
    },50);
    if (room) connect();
  } else {
    const attach = mobile => {
      if ($('remotePanel')) return;
      input = mobile;
      const panel = document.createElement('details'); panel.id='remotePanel';
      panel.innerHTML = '<summary>手机手柄 <span id="remoteStatus">未连接</span></summary><div id="remoteQR"></div><strong id="remoteCode"></strong><p>同一 Wi-Fi 下扫描（不要使用 localhost）</p><a id="remoteLink"></a><button id="remoteConnect">创建手柄房间</button>';
      const style = document.createElement('style');
      style.textContent = '#remotePanel{position:fixed;right:12px;top:12px;z-index:30;max-width:300px;padding:8px;background:#eaeed8;color:#163b4b;border:2px solid #276b80;font:14px system-ui}#remotePanel summary{cursor:pointer}#remoteQR svg{width:160px;height:160px}#remoteCode{display:block;font-size:26px;letter-spacing:5px}#remoteLink{display:block;overflow-wrap:anywhere}#remotePanel button{min-height:44px}';
      document.head.append(style); document.body.append(panel);
      $('remoteConnect').onclick = () => {stopped=false;connect();$('remoteConnect').hidden=true;};
    };
    if (window.poightInput) attach(window.poightInput);
    else window.addEventListener('poight-input-ready',e=>attach(e.detail),{once:true});
  }
  setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN && Date.now()-lastReceive > 25000) socket.close();
    else send({type:'ping',t:Date.now()});
  },5000);
  window.addEventListener('pagehide', () => {stopped=true;clearTimeout(timer);socket?.close();});
})();
