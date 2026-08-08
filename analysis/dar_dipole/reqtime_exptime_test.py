import pandas as pd, numpy as np
np.seterr(all='ignore')

df = pd.read_parquet('/Users/klaus/telemetry_mining-trunk/notebooks/data/dar_calibstars_dataset.parquet',
                     columns=['EXPID','X','Y','loss','airmass'])
pt = pd.read_csv('/Users/klaus/telemetry_mining-trunk/data/dar_exposure_pointing.csv',
                 usecols=['EXPID','parallactic','reqtime','exptime','airmass'])
pt['gap']=pt['reqtime']-pt['exptime']
pt=pt[(pt.reqtime>0)&(pt.exptime>0)&np.isfinite(pt.parallactic)]

# ---------- (1) commonality / systematics of the gap ----------
print("=== gap = reqtime - exptime (per exposure) ===")
g=pt['gap']
print(f"n exposures with valid times: {len(pt)}")
print(f"gap percentiles [5,25,50,75,95]: {np.percentile(g,[5,25,50,75,95]).round(0)}")
print(f"fraction gap>0 (exptime<reqtime): {(g>0).mean():.2f}   fraction |gap|<30s: {(abs(g)<30).mean():.2f}")
print(f"mean gap {g.mean():.0f}s   median {g.median():.0f}s")
# correlation of gap with airmass (the confound)
r=np.corrcoef(pt.gap, pt.airmass)[0,1]
print(f"corr(gap, airmass) = {r:+.3f}  (confound check)")
for lo,hi in [(1.0,1.2),(1.2,1.5),(1.5,1.8),(1.8,2.1)]:
    m=(pt.airmass>=lo)&(pt.airmass<hi)
    print(f"  airmass {lo}-{hi}: median gap {pt.gap[m].median():.0f}s  frac gap>0 {(pt.gap[m]>0).mean():.2f}  n={m.sum()}")

# ---------- (2) decisive: does D_rot scale with gap, at controlled airmass? ----------
df=df.merge(pt[['EXPID','parallactic','gap','airmass']].rename(columns={'airmass':'am_pt'}),on='EXPID',how='inner')
df=df[np.isfinite(df.loss)&df.loss.between(-0.3,0.3)&np.isfinite(df.X)&np.isfinite(df.Y)]
names=['rad','fdipx','fdipy','rdipx','rdipy','fq1','fq2','rq1','rq2']
def fit(sub):
    Rn=410.0; u=sub.X.values/Rn; v=sub.Y.values/Rn
    q=np.deg2rad(sub.parallactic.values); c,s=np.cos(q),np.sin(q)
    up=u*c+v*s; vp=-u*s+v*c
    M=np.column_stack([u*u+v*v,u,v,up,vp,u*u-v*v,2*u*v,up*up-vp*vp,2*up*vp])
    d=pd.DataFrame(M,columns=names); d['y']=sub.loss.values; d['e']=sub.EXPID.values
    gm=d.groupby('e')[names+['y']].transform('mean')
    Xd=(d[names]-gm[names]).values; yd=(d['y']-gm['y']).values
    b=np.linalg.lstsq(Xd,yd,rcond=None)[0]; dd=dict(zip(names,b))
    Drot=np.hypot(dd['rdipx'],dd['rdipy']); Qrot=np.hypot(dd['rq1'],dd['rq2'])
    ang=np.degrees(np.arctan2(dd['rdipy'],dd['rdipx']))
    return Drot,Qrot,ang

# control airmass: use a band, split by gap
band=df[(df.airmass>1.5)&(df.airmass<2.05)]
print("\n=== D_rot vs gap, controlled to airmass 1.5-2.05 ===")
print(f"{'gap bin':<16}{'n_exp':>7}{'mean_am':>9}{'mean_gap':>9}{'D_rot':>8}{'Q_rot':>8}{'dip_ang':>9}")
# terciles of gap within the band
qs=np.percentile(band.gap,[33,67])
def label(gv):
    return 'low' if gv<qs[0] else ('mid' if gv<qs[1] else 'high')
band=band.assign(gb=band.gap.map(label))
for gb in ['low','mid','high']:
    sub=band[band.gb==gb]
    Dr,Qr,ang=fit(sub)
    print(f"{gb+' (gap~'+str(int(sub.gap.median()))+'s)':<16}{sub.EXPID.nunique():>7}{sub.airmass.mean():>9.2f}{sub.gap.mean():>9.0f}{Dr:>8.4f}{Qr:>8.4f}{ang:>9.0f}")

# also explicit sign split: gap<0 vs gap>+300
print("\n=== sign test (airmass 1.5-2.05): does dipole flip direction with gap sign? ===")
for name,mask in [('gap < 0', band.gap<0),('gap 0-300', (band.gap>=0)&(band.gap<300)),('gap > 300', band.gap>=300)]:
    sub=band[mask]
    if sub.EXPID.nunique()<20:
        print(f"{name:<12} too few ({sub.EXPID.nunique()})"); continue
    Dr,Qr,ang=fit(sub)
    print(f"{name:<12} n_exp={sub.EXPID.nunique():>4} mean_gap={sub.gap.mean():>6.0f}s  D_rot={Dr:.4f}  dip_ang={ang:+.0f}")
