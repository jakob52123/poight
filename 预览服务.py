"""仅暴露游戏页面与构建清单中的资产。无目录浏览/写接口/源码/ROM暴露。"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,unquote
import argparse,gzip,json,mimetypes,hashlib
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--candidate',action='store_true');ap.add_argument('--port',type=int,default=8791);ap.add_argument('--host',default='localhost');args=ap.parse_args()
PAGE=ROOT/('候选试玩.html' if args.candidate else 'index.html');cache={};manifest_mtime=None;allowed=set()

def refresh_manifest():
    global manifest_mtime,allowed
    p=ROOT/('候选发布清单.json' if args.candidate else '发布清单.json');mtime=p.stat().st_mtime_ns
    if mtime!=manifest_mtime:
        d=json.loads(p.read_text());allowed={('/'+n) for n in d['assets'] if Path(n).parts[0]=='assets' and len(Path(n).parts)==2};manifest_mtime=mtime

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def do_HEAD(self):self.serve(True)
    def do_GET(self):self.serve(False)
    def do_POST(self):self.send_error(405)
    def serve(self,head):
        try:
            path=unquote(urlsplit(self.path).path)
            if '\\' in path or '\0' in path or any(p in ('.','..') for p in path.split('/')):self.send_error(404);return
            refresh_manifest()
            if path in ('/','/index.html'):file=PAGE;mime='text/html; charset=utf-8';main=True
            elif path in allowed:file=ROOT/path.lstrip('/');mime='image/png' if file.suffix=='.png' else 'text/plain; charset=utf-8';main=False
            else:self.send_error(404);return
            stat=file.stat();key=(str(file),stat.st_mtime_ns,stat.st_size)
            item=cache.get(key)
            if item is None:
                data=file.read_bytes();compressed=gzip.compress(data,compresslevel=6) if not mime.startswith('image/') else None
                item=(data,compressed,hashlib.sha256(data).hexdigest());cache[key]=item
                if len(cache)>512:
                    for k in list(cache)[:128]:cache.pop(k,None)
            data,compressed,digest=item;use_gzip=compressed is not None and 'gzip' in self.headers.get('Accept-Encoding','')
            etag='"'+digest+'"'
            if not main and self.headers.get('If-None-Match')==etag:
                self.send_response(304);self.send_header('ETag',etag);self.send_header('Content-Length','0');self.end_headers();return
            body=compressed if use_gzip else data
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store' if main else 'private, max-age=31536000, immutable');self.send_header('ETag',etag);self.send_header('Vary','Accept-Encoding');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
            if main:self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if use_gzip:self.send_header('Content-Encoding','gzip')
            self.end_headers()
            if not head:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
        except FileNotFoundError:self.send_error(404)
    def log_message(self,format,*args):pass

print(f'Pocket arena on http://{args.host}:{args.port}/ ({PAGE.name})',flush=True)
ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
