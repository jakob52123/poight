"""Small bounded RFC6455 text relay for 预览服务.py; Python stdlib only."""
import base64
import hashlib
import json
import queue
import secrets
import socket
import struct
import threading
import time

LOCK = threading.RLock()
ROOMS = {}

class Peer:
    def __init__(self, handler):
        self.h = handler
        self.out = queue.Queue(maxsize=64)
        self.done = threading.Event()
        self.worker = threading.Thread(target=self.write, daemon=True)
        self.worker.start()
    def send(self, obj):
        data = json.dumps(obj, separators=(',', ':')).encode()
        try: self.out.put_nowait(bytes([0x81]) + (bytes([len(data)]) if len(data)<126 else b'\x7e'+struct.pack('!H',len(data))) + data)
        except queue.Full:
            try: self.h.connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
    def write(self):
        try:
            while True:
                try: data = self.out.get(timeout=.5)
                except queue.Empty:
                    if self.done.is_set(): return
                    continue
                if data is None: return
                self.h.connection.sendall(data)
        except OSError:
            try: self.h.connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
    def close(self):
        self.done.set()
        try: self.out.put_nowait(None)
        except queue.Full: pass
        self.worker.join(timeout=.1)

def upgrade(h):
    # Same-origin only; possession of a random room code grants controller access.
    from urllib.parse import urlsplit
    origin = h.headers.get('Origin', '')
    if urlsplit(origin).netloc != h.headers.get('Host') or h.headers.get('Sec-WebSocket-Version') != '13':
        h.send_error(403); return
    try:
        key = h.headers['Sec-WebSocket-Key']
        if len(base64.b64decode(key, validate=True)) != 16: raise ValueError()
    except (ValueError, TypeError):
        h.send_error(400); return
    h.send_response(101)
    h.send_header('Upgrade','websocket'); h.send_header('Connection','Upgrade')
    h.send_header('Sec-WebSocket-Accept',base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode())
    h.end_headers(); h.close_connection = True
    peer = Peer(h); room = None; role = None
    rate_start = time.monotonic(); count = 0
    h.connection.settimeout(30)
    def exact(n):
        b = h.rfile.read(n)
        if len(b) != n: raise EOFError()
        return b
    try:
        while True:
            a,b = exact(2)
            if not a & 128 or not b & 128: break  # no fragmentation / unmasked clients
            size = b & 127
            if size == 127: break  # 64-bit lengths are never needed for bounded input
            if size == 126: size = struct.unpack('!H',exact(2))[0]
            if size > 2048: break
            mask = exact(4); raw = exact(size)
            raw = bytes(v ^ mask[i%4] for i,v in enumerate(raw))
            if a & 15 == 8: break
            if a & 15 != 1: break
            msg = json.loads(raw)
            if not isinstance(msg, dict): break
            now = time.monotonic()
            if now-rate_start >= 1: rate_start = now; count = 0
            count += 1
            if count > 200: break
            with LOCK:
                now = time.monotonic()
                for code,r in list(ROOMS.items()):
                    if not r['host'] and not r['phone'] and now-r['seen'] > 300: ROOMS.pop(code)
                if not room:
                    role = msg.get('role')
                    if role == 'host':
                        code = msg.get('room'); r = ROOMS.get(code)
                        if r and secrets.compare_digest(str(msg.get('token','')),r['token']):
                            old = r['host']; room = r; r['host'] = peer
                            if old:
                                try: old.h.connection.shutdown(socket.SHUT_RDWR)
                                except OSError: pass
                        else:
                            if len(ROOMS) >= 100: break
                            code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
                            while code in ROOMS:
                                code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
                            room = {'host':peer,'phone':None,'token':secrets.token_urlsafe(24),'phoneToken':secrets.token_urlsafe(24),'seen':now,'code':code}
                            ROOMS[code] = room
                        peer.send({'type':'room','room':code,'token':room['token'],'connected':bool(room['phone'])})
                        if room['phone']: room['phone'].send({'type':'status','connected':True})
                    elif role == 'phone':
                        room = ROOMS.get(str(msg.get('room','')).upper())
                        if not room or (room['phone'] and not secrets.compare_digest(str(msg.get('token','')), room['phoneToken'])):
                            peer.send({'type':'error','message':'房间不存在或手柄已占用'}); room = None; break
                        old = room['phone']
                        room['phone'] = peer
                        if old:
                            try: old.h.connection.shutdown(socket.SHUT_RDWR)
                            except OSError: pass
                        peer.send({'type':'joined','token':room['phoneToken']})
                        if not room['host']: peer.send({'type':'status','connected':False})
                        if room['host']: room['host'].send({'type':'status','connected':True})
                    else: break
                elif msg.get('type') == 'ping':
                    peer.send({'type':'pong','t':msg.get('t')})
                elif role == 'phone' and msg.get('type') == 'input':
                    # Only bounded input events; no game state or arbitrary command execution.
                    x,y = float(msg.get('x',0)),float(msg.get('y',0))
                    if not (-1 <= x <= 1 and -1 <= y <= 1): break
                    action = msg.get('action')
                    if action not in (None,'start','dash','jump','move0','move1','move2','move3'): break
                    seq = msg.get('seq')
                    if not isinstance(seq, int) or not 0 <= seq < 2**53: break
                    if room['host']: room['host'].send({'type':'input','x':x,'y':y,'action':action,'seq':seq})
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        pass
    finally:
        with LOCK:
            if room and room.get(role) is peer:
                room[role] = None; room['seen'] = time.monotonic()
                other = room.get('host' if role == 'phone' else 'phone')
                if other:
                    try: other.send({'type':'status','connected':False})
                    except OSError: pass
        peer.close()
