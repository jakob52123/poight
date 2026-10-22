"""Wire-level relay regression; stdlib only, no game assets/browser required.
Run: python3 -m unittest discover -s tests -p test_phone_relay.py -v
"""
import base64
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Wire:
    def __init__(self, port, origin=None):
        self.socket = socket.create_connection(('127.0.0.1', port), timeout=2)
        self.socket.settimeout(2)
        self.stream = self.socket.makefile('rb')
        key = base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall((f'GET /relay HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'
                             f'Origin: {origin or "http://127.0.0.1:"+str(port)}\r\n'
                             f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                             f'Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\n\r\n').encode())
        self.status = self.stream.readline()
        while self.stream.readline() not in (b'\r\n', b''):
            pass

    def send(self, message, padded_length=0):
        raw = json.dumps(message, separators=(',', ':')).encode()
        raw += b' ' * max(0, padded_length - len(raw))
        mask = os.urandom(4)
        size = len(raw)
        header = bytes([0x81, 0x80 | size]) if size < 126 else bytes([0x81, 0x80 | 126]) + struct.pack('!H', size)
        self.socket.sendall(header + mask + bytes(v ^ mask[i % 4] for i, v in enumerate(raw)))

    def receive(self):
        header = self.stream.read(2)
        if not header:
            raise EOFError()
        assert len(header) == 2 and header[0] == 0x81
        size = header[1] & 127
        if size == 126:
            size = struct.unpack('!H', self.stream.read(2))[0]
        return json.loads(self.stream.read(size))

    def close(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.stream.close()
        self.socket.close()

class RelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            cls.port = probe.getsockname()[1]
        cls.server = subprocess.Popen(['python3', str(ROOT/'预览服务.py'), '--host', '127.0.0.1', '--port', str(cls.port)],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1', cls.port), timeout=.1):
                    return
            except OSError:
                time.sleep(.02)
        cls.server.terminate()
        raise RuntimeError('preview server failed to start')

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=5)

    def setUp(self):
        self.peers = []

    def tearDown(self):
        for peer in self.peers:
            peer.close()

    def peer(self, origin=None):
        peer = Wire(self.port, origin)
        self.peers.append(peer)
        return peer

    def paired(self):
        host = self.peer()
        host.send({'role': 'host'})
        room = host.receive()
        phone = self.peer()
        phone.send({'role': 'phone', 'room': room['room']})
        self.assertEqual(phone.receive()['type'], 'joined')
        self.assertTrue(host.receive()['connected'])
        return host, phone, room

    def test_origin_rejected(self):
        self.assertIn(b'403', self.peer('https://untrusted.example').status)

    def test_input_extended_length_127_and_validation(self):
        host, phone, _ = self.paired()
        # 127 is a legitimate payload length, not the 64-bit-length opcode.
        phone.send({'type': 'input', 'x': .5, 'y': -.25, 'action': 'dash', 'seq': 7}, padded_length=127)
        packet = host.receive()
        self.assertEqual(packet['type'], 'input')
        self.assertEqual((packet['x'], packet['y'], packet['action'], packet['seq']), (.5, -.25, 'dash', 7))
        phone.send({'type': 'input', 'x': 2, 'y': 0, 'seq': 8})
        self.assertEqual(host.receive(), {'type': 'status', 'connected': False})

    def test_host_resume_and_phone_status(self):
        host, phone, room = self.paired()
        host.close()
        self.peers.remove(host)
        self.assertFalse(phone.receive()['connected'])
        resumed = self.peer()
        resumed.send({'role': 'host', 'room': room['room'], 'token': room['token']})
        self.assertEqual(resumed.receive()['room'], room['room'])
        self.assertTrue(phone.receive()['connected'])

    def test_token_resume_replaces_half_open_host(self):
        _, phone, room = self.paired()
        resumed = self.peer()
        resumed.send({'role': 'host', 'room': room['room'], 'token': room['token']})
        self.assertEqual(resumed.receive()['room'], room['room'])
        self.assertTrue(phone.receive()['connected'])
        phone.send({'type': 'input', 'x': 0, 'y': 1, 'seq': 1})
        self.assertEqual(resumed.receive()['y'], 1)

    def test_second_phone_rejected(self):
        host, _, room = self.paired()
        extra = self.peer()
        extra.send({'role': 'phone', 'room': room['room']})
        self.assertEqual(extra.receive()['type'], 'error')
        # Rejected guest must not clear the legitimate peer or its input route.
        self.assertIn(b'101', host.status)

if __name__ == '__main__':
    unittest.main()
