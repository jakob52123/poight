"""只读解码已下载的FireRed瓦片：8×8 tile、16色pal、翻转位和双层16×16 metatile。"""
from pathlib import Path
from PIL import Image, ImageDraw
import hashlib
import json
import struct

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'原始'
source=json.loads((SRC/'来源.json').read_text())
for row in source['files']:
    assert 'error' not in row
    assert hashlib.sha256((SRC/row['local']).read_bytes()).hexdigest()==row['sha256']
indexed=Image.open(SRC/'tiles.png')
assert indexed.mode=='P' and indexed.size==(128,320) and indexed.getextrema()==(0,15)
palettes=[]
for n in range(16):
    lines=(SRC/f'palettes/{n:02d}.pal').read_text().splitlines()
    assert lines[:3]==['JASC-PAL','0100','16']
    colors=[tuple(map(int,line.split())) for line in lines[3:] if line.strip()]
    assert len(colors)==16 and all(len(c)==3 and all(0<=v<=255 for v in c) for c in colors)
    palettes.append(colors)
words=struct.unpack('<5120H',(SRC/'metatiles.bin').read_bytes())
atlas=Image.new('RGBA',(256,640));bottom=Image.new('RGBA',atlas.size);top=Image.new('RGBA',atlas.size)
used=set();pal_used=set()
for m in range(640):
    layers=[Image.new('RGBA',(16,16)),Image.new('RGBA',(16,16))]
    for position,word in enumerate(words[m*8:m*8+8]):
        tile=word&1023;palette=word>>12;used.add(tile);pal_used.add(palette)
        assert tile<640 and palette<7
        raw=indexed.crop((tile%16*8,tile//16*8,tile%16*8+8,tile//16*8+8))
        rgba=Image.new('RGBA',(8,8));rgba.putdata([(*palettes[palette][i],255 if i else 0) for i in raw.get_flattened_data()])
        if word&0x400:rgba=rgba.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if word&0x800:rgba=rgba.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        layers[position//4].alpha_composite(rgba,((position%2)*8,(position%4//2)*8))
    xy=(m%16*16,m//16*16)
    bottom.paste(layers[0],xy);top.paste(layers[1],xy)
    layers[0].alpha_composite(layers[1]);atlas.paste(layers[0],xy)
atlas.save(ROOT/'元瓦片.png',optimize=True);bottom.save(ROOT/'底层.png',optimize=True);top.save(ROOT/'上层.png',optimize=True)
for start in (0,256,512):
    end=min(640,start+256);sheet=Image.new('RGB',(16*58,((end-start+15)//16)*68),(226,234,214));d=ImageDraw.Draw(sheet)
    for i,m in enumerate(range(start,end)):
        tile=atlas.crop((m%16*16,m//16*16,m%16*16+16,m//16*16+16)).resize((48,48),Image.Resampling.NEAREST)
        x=i%16*58+5;y=i//16*68+17
        d.text((x,y-14),f'{m:03X}',fill=(34,48,34));sheet.paste(tile,(x,y),tile)
    sheet.save(ROOT/f'瓦片索引-{start:03X}.png')
audit={'commit':source['commit'],'sourceFilesVerified':len(source['files']),'tiles':640,'metatiles':640,'paletteSlots':sorted(pal_used),'tileBits':'index 0..9, hflip 10, vflip 11, palette 12..15','metatileOrder':'bottom TL TR BL BR; upper TL TR BL BR','transparentIndex':0,'noROMDownloaded':True,'outputRGBA':[256,640],'atlasSHA256':hashlib.sha256((ROOT/'元瓦片.png').read_bytes()).hexdigest()}
(ROOT/'解码核验.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(audit,ensure_ascii=False))
