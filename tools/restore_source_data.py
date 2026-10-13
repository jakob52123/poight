#!/usr/bin/env python3
"""Restore losslessly packed source JSONs; not a game asset downloader."""
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent


def restore(root=ROOT):
    rows = json.loads((root / 'tools/source-data.json').read_text())
    pending = []
    for row in rows:
        path = PurePosixPath(row['path'])
        if path.is_absolute() or any(part in ('.git', '..') for part in path.parts) or path.suffix != '.json':
            raise ValueError('Unsafe source-data path')
        target = root / str(path)
        packed = root / (str(path) + '.gz')
        if not target.resolve().is_relative_to(root.resolve()) or not packed.resolve().is_relative_to(root.resolve()):
            raise ValueError('Source-data symlink escape')
        blob = packed.read_bytes()
        if hashlib.sha256(blob).hexdigest() != row['packedSHA256']:
            raise ValueError('Packed source-data SHA mismatch: ' + str(path))
        data = gzip.decompress(blob)
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Restored source-data SHA mismatch: ' + str(path))
        json.loads(data)
        pending.append((target, data))
    for target, data in pending:
        target.write_bytes(data)
    print(f'Restored {len(pending)} source JSON files; SHA256 verified; no network.')


if __name__ == '__main__':
    restore()
