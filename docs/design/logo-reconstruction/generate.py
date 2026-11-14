"""Render the actual source stroke and its eightfold reconstruction, without redesigning it."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[2]/'frontend/public/brand/reconstruction'
TRACE=json.loads((HERE/'trace.json').read_text(encoding='utf-8'))
POINTS=TRACE['points']
PIVOT=tuple(TRACE['pivot'])

def xy(p):return ' '.join(f'{v:.3f}'.rstrip('0').rstrip('.') for v in p)

def smooth_path(points):
    # These are outline points, not an invented replacement centerline.
    filtered=[tuple(sum(points[(i+j)%len(points)][k] for j in range(-2,3))/5 for k in (0,1)) for i in range(len(points))]
    path='M'+xy(filtered[0])
    for i,p in enumerate(filtered):
        before=filtered[(i-1)%len(filtered)];after=filtered[(i+1)%len(filtered)];following=filtered[(i+2)%len(filtered)]
        c1=tuple(p[k]+(after[k]-before[k])/6 for k in (0,1))
        c2=tuple(after[k]-(following[k]-p[k])/6 for k in (0,1))
        path+='C'+xy(c1)+' '+xy(c2)+' '+xy(after)
    return path+'Z'

def render(path,name,master=False):
    box='1090 315 575 1340' if master else '730 315 1340 1340'
    body='<use href="#source-s"/>' if master else ''.join(f'<use href="#source-s" transform="rotate({i*45} {PIVOT[0]} {PIVOT[1]})"/>' for i in range(8))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" fill="#18212b" role="img" aria-labelledby="title"><title id="title">{name}</title><desc>Derived directly from Untitled_Artwork_2.png. Source stroke contour and internal negative spaces preserved. No central cutout, artificial weaving, inset ornament, or joined ray tips. Transparent background.</desc><defs><path id="source-s" d="{path}"/></defs>{body}</svg>'

OUT.mkdir(parents=True,exist_ok=True)
for filename,path,master in [('traced-s',TRACE['path'],True),('cleaned-s',smooth_path(POINTS),True),('direct-reconstruction',TRACE['path'],False),('starry-eye',smooth_path(POINTS),False)]:
    (OUT/f'{filename}.svg').write_text(render(path,'Stellaris — '+filename.replace('-',' '),master),encoding='utf-8')
print('Rendered direct and edge-cleaned reconstructions from the original source contour.')
