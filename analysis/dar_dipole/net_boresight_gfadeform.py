import numpy as np, re
np.seterr(all='ignore')

# --- GFA geometry from Steve's gfadata file ---
G={}
for line in open('/Users/klaus/telemetry_mining-trunk/pm363330/gfadata-363330.5.par'):
    m=re.match(r'^(\d+),(rot|xoff|yoff)\s+([-\d.eE]+)',line.strip())
    if m:
        gid=int(m.group(1)); G.setdefault(gid,{})[m.group(2)]=float(m.group(3))
pa={}; rot={}
for gid,d in G.items():
    pa[gid]=np.degrees(np.arctan2(d['yoff'],d['xoff'])); rot[gid]=d['rot']
gids=sorted(G)
print("GFA geometry from PlateMaker gfadata:")
for g in gids:
    print("  GFA %2d: pa=%+7.1f  rot=%+6.1f  (rot-pa=%+.1f)"%(g,pa[g],rot[g],rot[g]-pa[g]))
pav=np.array([pa[g] for g in gids])
print("  sum unit vecs: (%+.2f,%+.2f)  (0,0)=balanced"%(np.cos(np.radians(pav)).sum(),np.sin(np.radians(pav)).sum()))

# --- deformation model ---
D={}
for line in open('/Users/klaus/telemetry_mining-trunk/gfadeform.dat'):
    line=line.strip()
    if not line or line[0]=='#': continue
    p=line.split(); D[(p[0],p[1],p[2],p[3])]=[float(x) for x in p[4:7]]
def poly(c,t): return c[0]+c[1]*t+c[2]*t*t
def gcomp(side,ha,tanz,parel):
    rp=np.radians(parel); out=[]
    for xy in ['x','y']:
        R={l:poly(D[(side,ha,xy,l)],tanz) for l in ['offset','cosp','sinp','cos2p','sin2p']}
        out.append(R['offset']+R['cosp']*np.cos(rp)+R['sinp']*np.sin(rp)+R['cos2p']*np.cos(2*rp)+R['sin2p']*np.sin(2*rp))
    return out[0],out[1]
def net(psi,am):
    zd=np.degrees(np.arccos(1/am)); tanz=np.tan(np.radians(zd))
    side='south' if -90<psi<90 else 'north'
    ha='east' if psi<0 else 'west'
    if abs(psi)<25 and zd>57.5 and (side,'both','x','offset') in D: ha='both'
    dxs=[];dys=[]
    for g in gids:
        parel=pa[g]-psi-90.
        dx,dy=gcomp(side,ha,tanz,parel)
        rr=np.radians(rot[g]-psi)
        dxs.append(dx*np.cos(rr)-dy*np.sin(rr)); dys.append(dy*np.cos(rr)+dx*np.sin(rr))
    return np.mean(dxs),np.mean(dys),np.median(np.hypot(dxs,dys))  # arcsec

print("\nNet boresight = mean over 6 GFAs (arcsec).  D_rot dipole = 10um = 0.14 arcsec.")
print("%8s %13s %10s %13s"%("airmass","median|net|","max|net|","per-GFA typ"))
for am in [1.2,1.6,2.0]:
    psis=np.arange(-175,176,5.)
    res=[net(p,am) for p in psis]
    netmag=[np.hypot(r[0],r[1]) for r in res]
    perg=[r[2] for r in res]
    print("%8.1f %13.3f %10.3f %13.3f"%(am,np.median(netmag),np.max(netmag),np.median(perg)))

print("\nDoes net rotate with psi & grow with airmass? (airmass 2.0)")
for p in [-150,-90,-30,30,90,150]:
    dx,dy,typ=net(p,2.0)
    print("  psi=%+5d: net=(%+.3f,%+.3f) |%.3f| ang=%+.0f"%(p,dx,dy,np.hypot(dx,dy),np.degrees(np.arctan2(dy,dx))))

psi0,zd0=-28.4947,30.8485; am0=1/np.cos(np.radians(zd0))
dx,dy,typ=net(psi0,am0)
print("\nThis exposure (psi=%.1f, zd=%.1f, airmass=%.3f): net=(%+.3f,%+.3f) |%.3f| arcsec = %.1f um"%(psi0,zd0,am0,dx,dy,np.hypot(dx,dy),np.hypot(dx,dy)*70))
