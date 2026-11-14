"""Build the three sketch-derived logo candidates using only the Python standard library."""
from pathlib import Path
import math
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'frontend/public/brand/candidates'
OUT.mkdir(parents=True, exist_ok=True)

# One continuous S. Opposite copies share tips but separate along their tails.
SEGMENTS = [
    ((-185, -470), (-180, -375), (-162, -220), (-142, -150)),
    ((-142, -150), (-131, -100), (-95, -53), (-38, -50)),
    ((-38, -50), (35, -46), (117, -88), (137, -32)),
    ((137, -32), (155, 20), (109, 85), (82, 128)),
    ((82, 128), (118, 227), (160, 370), (185, 470)),
]

def point(seg, t):
    return tuple((1-t)**3*seg[0][i]+3*(1-t)**2*t*seg[1][i]+3*(1-t)*t*t*seg[2][i]+t**3*seg[3][i] for i in (0, 1))

def num(v):
    return f'{v:.3f}'.rstrip('0').rstrip('.')

def xy(p):
    return ' '.join(map(num, p))

MASTER = 'M'+xy(SEGMENTS[0][0])+''.join('C'+' '.join(xy(p) for p in seg[1:]) for seg in SEGMENTS)
SAMPLES = [point(seg, i/64) for seg in SEGMENTS for i in range(64)] + [SEGMENTS[-1][-1]]

def rotate(p, angle):
    a=math.radians(angle)
    return (p[0]*math.cos(a)-p[1]*math.sin(a), p[0]*math.sin(a)+p[1]*math.cos(a))

def smooth_outline(points):
    """Interpolate sampled normal offsets with tangent-continuous cubic segments."""
    path='M'+xy(points[0])
    for i in range(len(points)):
        p0,p1,p2,p3=[points[j % len(points)] for j in (i-1,i,i+1,i+2)]
        c1=tuple(p1[k]+(p2[k]-p0[k])/6 for k in (0,1))
        c2=tuple(p2[k]-(p3[k]-p1[k])/6 for k in (0,1))
        path+='C'+xy(c1)+' '+xy(c2)+' '+xy(p2)
    return path+'Z'

def calligraphic_outline():
    left,right=[],[]
    for i,p in enumerate(SAMPLES):
        before=SAMPLES[max(0,i-1)]; after=SAMPLES[min(len(SAMPLES)-1,i+1)]
        dx,dy=after[0]-before[0],after[1]-before[1]
        length=math.hypot(dx,dy)
        radius=math.hypot(*p)
        # Heavy, flowing bends transition into fine, pointed long tails.
        width=5+13*math.exp(-((radius-125)/130)**2)
        edge=min(i,len(SAMPLES)-1-i)
        width*=min(1,edge/12)
        nx,ny=-dy/length*width/2,dx/length*width/2
        left.append((p[0]+nx,p[1]+ny)); right.append((p[0]-nx,p[1]-ny))
    return smooth_outline(left+right[::-1])

def intersections(a,b):
    found=[]
    for p,q in zip(a,a[1:]):
        rx,ry=q[0]-p[0],q[1]-p[1]
        for u,v in zip(b,b[1:]):
            sx,sy=v[0]-u[0],v[1]-u[1]
            det=rx*sy-ry*sx
            if abs(det)<1e-8: continue
            dx,dy=u[0]-p[0],u[1]-p[1]
            t=(dx*sy-dy*sx)/det; z=(dx*ry-dy*rx)/det
            if 0<t<1 and 0<z<1:
                found.append((p[0]+t*rx,p[1]+t*ry))
    return found

crossings=intersections(SAMPLES,[rotate(p,45) for p in SAMPLES])
eligible=[p for p in crossings if 85<math.hypot(*p)<185]
if not eligible:
    raise RuntimeError('No suitable repeated central weave crossing.')
WEAVE=min(eligible,key=lambda p:abs(math.hypot(*p)-130))

def svg(treatment, master_only=False):
    title={'a':'Faithful cleaned trace','b':'Calligraphic trace','c':'Ornamental woven trace','master':'Master S-shaped bolt'}[treatment]
    defs=f'<path id="s-bolt" d="{MASTER}"/>'
    if treatment=='b':
        defs=f'<path id="s-bolt" d="{calligraphic_outline()}"/>'
    if treatment=='c':
        defs+=f'<mask id="weave" maskUnits="userSpaceOnUse" x="-540" y="-540" width="1080" height="1080"><path fill="white" d="M-540-540H540V540H-540Z"/><circle cx="{num(WEAVE[0])}" cy="{num(WEAVE[1])}" r="13" fill="black"/></mask>'
    copies=1 if master_only else 8
    stroke='none' if treatment=='b' else 'currentColor'
    fill='currentColor' if treatment=='b' else 'none'
    if treatment=='c':
        body=''.join(f'<g transform="rotate({i*45})"><use href="#s-bolt" mask="url(#weave)"/></g>' for i in range(copies))
    else:
        body=''.join(f'<use href="#s-bolt" transform="rotate({i*45})"/>' for i in range(copies))
    if treatment=='c':
        # A single inset follows each long eye, stopping well before the shared tip.
        paired_tail=tuple(tuple((a-b)/2 for a,b in zip(p,q)) for p,q in zip(SEGMENTS[0],reversed(SEGMENTS[-1])))
        inset_points=[point(paired_tail,.18+i*.64/32) for i in range(33)]
        inset='M'+xy(inset_points[0])+''.join('L'+xy(p) for p in inset_points[1:])
        body+=''.join(f'<path d="{inset}" transform="rotate({i*45})" stroke-width="3.5"/>' for i in range(8))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-540 -540 1080 1080" fill="{fill}" stroke="{stroke}" stroke-width="15" stroke-linecap="round" stroke-linejoin="round" color="#185abc" role="img" aria-labelledby="title"><title id="title">Stellaris — {title}</title><desc>One continuous S-shaped lightning bolt, repeated at 45-degree intervals. Traced and regularized from the user's original sketch. Transparent background. No central cutout.</desc><defs>{defs}</defs>{body}</svg>'''

for variant in ['a','b','c']:
    (OUT/f'stellaris-{variant}.svg').write_text(svg(variant),encoding='utf-8')
(OUT/'master-s.svg').write_text(svg('master',True),encoding='utf-8')
if len(sys.argv)>1:
    shutil.copyfile(sys.argv[1],OUT/'original-sketch.png')
print(f'Built three treatments and master S in {OUT}. Weave crossing: {xy(WEAVE)}')
