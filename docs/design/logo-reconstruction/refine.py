"""Preserve the accepted iris while shortening and cleaning its outer rays."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[2]/'frontend/public/brand'
trace=json.loads((HERE/'trace.json').read_text(encoding='utf-8'))
points=trace['points']
cx,cy=trace['pivot']

def xy(p):return ' '.join(f'{v:.3f}'.rstrip('0').rstrip('.') for v in p)

filtered=[tuple(sum(points[(i+j)%len(points)][k] for j in range(-2,3))/5 for k in (0,1)) for i in range(len(points))]
path='M'+xy(filtered[0])
for i,p in enumerate(filtered):
    a=filtered[(i-1)%len(filtered)];b=filtered[(i+1)%len(filtered)];c=filtered[(i+2)%len(filtered)]
    path+='C'+xy(tuple(p[k]+(b[k]-a[k])/6 for k in (0,1)))+' '+xy(tuple(b[k]-(c[k]-p[k])/6 for k in (0,1)))+' '+xy(b)
path+='Z'

# Keep the original overlapping iris. Outside it, replace the long doubled
# contours with one constant-width, round-ended curve per direction.
ray='M1504 1129C1458 1205 1395 1325 1255 1375'
uses=''.join(f'<g transform="rotate({i*45} {cx} {cy})"><use href="#primary-ray"/></g>' for i in range(8))
iris=''.join(f'<g transform="rotate({i*45} {cx} {cy})"><g clip-path="url(#source-bends)"><use href="#source-s"/></g><circle cx="1298" cy="785" r="13"/><circle cx="1442" cy="1215" r="13"/></g>' for i in range(8))
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="920 513 940 940" fill="currentColor" color="#41464e" role="img" aria-labelledby="title"><title id="title">Stellaris focused research eye</title><desc>The accepted source-traced mandala with eight shorter smooth round-ended primary rays. The secondary contour ends at the iris. No detached decorative accents.</desc><defs><path id="source-s" d="{path}"/><path id="primary-ray" d="{ray}" fill="none" stroke="currentColor" stroke-width="26" stroke-linecap="round"/><clipPath id="source-bends"><path d="M1000 785H1800V1215H1000Z"/></clipPath></defs><g id="stellaris-mark">{uses}{iris}</g></svg>'''
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'stellaris-mark.svg').write_text(svg,encoding='utf-8')
print('Updated the graphite research-eye asset: original iris, eight shorter primary rays, no long secondary rays.')
