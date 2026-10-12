"""Original Emerald grass field effects, indexed palette decoding only."""
from pathlib import Path
import re,json,hashlib
from PIL import Image
ROOT=Path(__file__).resolve().parent;SRC=ROOT/'原始/pokeemerald';OUT=ROOT/'丰缘西南'
def build_grass():
 OUT.mkdir(exist_ok=True);palette=SRC/'graphics/field_effects/palettes/general_1.pal';defs=SRC/'src/data/field_effects/field_effect_objects.h';helpers=SRC/'src/field_effect_helpers.c'
 lines=palette.read_text().splitlines();assert lines[:3]==['JASC-PAL','0100','16'];colors=[tuple(map(int,line.split())) for line in lines[3:] if line.strip()];assert len(colors)==16
 code=defs.read_text();result={};sources=[palette,defs,helpers]
 for name,symbol,behaviors in [('tall','TallGrass',[2]),('long','LongGrass',[3,9])]:
  path=SRC/f'graphics/field_effects/pics/{name}_grass.png';sources.append(path);im=Image.open(path);assert im.mode=='P' and im.height==16 and im.width%16==0
  rgba=Image.new('RGBA',im.size);rgba.putdata([(*colors[i],0 if i==0 else 255) for i in im.get_flattened_data()]);output=OUT/(name+'-grass.png');rgba.save(output,optimize=True)
  body=re.search(r'sAnim_'+symbol+r'\[\]\s*=\s*\{(.*?)\};',code,re.S).group(1);sequence=[{'frame':int(f),'duration':int(d)/60} for f,d in re.findall(r'ANIMCMD_FRAME\((\d+),\s*(\d+)\)',body)];assert sequence and all(x['frame']<im.width//16 for x in sequence)
  b=output.read_bytes();result[name]={'path':str(output.relative_to(ROOT)),'sha256':hashlib.sha256(b).hexdigest(),'frameWidth':16,'frameHeight':16,'frames':im.width//16,'sequence':sequence,'duration':sum(x['duration'] for x in sequence),'idleFrame':0,'behaviors':behaviors}
 receipt={'source':'https://github.com/pret/pokeemerald','commit':'731ad5bfd6e6f265508d0efcca0ba42f9dcf5881','fieldEffectPalette':'FLDEFF_PAL_TAG_GENERAL_1','transparentIndex':0,'processing':'Original indexed pixels + original palette; alpha only at index 0. No drawing, generation, paid API or ROM.','fpsBasis':60,'runtimeAdaptation':'Grid entry via 8-direction real-time movement; excludes airborne actors; stationary final frame retained; no encounters or wild-spawn behavior.','files':[{'path':str(p.relative_to(SRC)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],'effects':result}
 (OUT/'草丛来源.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');return result
if __name__=='__main__':print(json.dumps(build_grass(),ensure_ascii=False,indent=2))
