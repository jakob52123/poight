"""Materialize R200 lazy literals only for historical runtimes predating the loader.
This changes fixture transport, never historical JS, pixels, anchors or assertions.
"""
import json


def materialize_character_packs(data, root):
    roster = {c['id']: c for c in data['roster']}
    for ident, refs in data.get('characterPacks', {}).items():
        text = (root / refs['offline']).read_text()
        prefix = f'window.PoightOfflineArt[{int(ident)}]='
        assert text.startswith(prefix) and text.endswith(';\n')
        value = json.loads(text[len(prefix):-2])
        data['art'][str(ident)] = value['art']
        roster[int(ident)]['moveAnchors'] = value['moveAnchors']
    return data
