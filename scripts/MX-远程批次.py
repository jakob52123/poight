"""Run one isolated shard with verified historical inputs, no global writes."""
import hashlib
import json
import os
import runpy
import signal
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
with tarfile.open(ROOT / 'MX-夹具.tar.gz') as archive:
    archive.extractall(ROOT, filter='data')
hashes = json.loads((ROOT / 'MX-夹具-sha256.json').read_text())
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
           for name, digest in hashes.items())
print(f'Verified {len(hashes)} unchanged historical inputs', flush=True)
os.environ.update(POIGHT_EXPLICIT_SUITES='1',
                  POIGHT_T5_BASELINE=str(ROOT / '验收记录/MX-夹具/T5'),
                  POIGHT_A1_REFERENCE=str(ROOT / '验收记录/MX-夹具/关键帧核查.jpg'),
                  PATH=str(ROOT / 'MX-远程bin') + os.pathsep + os.environ['PATH'])
server = None
if '--performance' in sys.argv:
    from urllib.parse import urlparse
    sys.argv.remove('--performance')
    port = str(urlparse(os.environ['POIGHT_TEST_URL']).port)
    pids = subprocess.check_output(['lsof', '-ti', 'tcp:' + port, '-sTCP:LISTEN'], text=True)
    for pid in pids.split():
        command = subprocess.check_output(['ps', '-o', 'command=', '-p', pid], text=True)
        assert '预览服务.py' in command and port in command, command
        os.kill(int(pid), signal.SIGTERM)
    subprocess.run([sys.executable, '验收-丰缘性能.py'], check=True)
    log = (ROOT / '验收记录/MX-performance-preview.log').open('w')
    server = subprocess.Popen([sys.executable, '预览服务.py', '--candidate', '--host',
                               'localhost', '--port', port], stdout=log, stderr=log)
try:
    runpy.run_path(str(ROOT / '验收记录/集成批次/run.py'), run_name='__main__')
finally:
    if server is not None:
        command = subprocess.check_output(['ps', '-o', 'command=', '-p', str(server.pid)], text=True)
        if '预览服务.py' in command and port in command:
            server.terminate()
            server.wait(timeout=10)
        log.close()
