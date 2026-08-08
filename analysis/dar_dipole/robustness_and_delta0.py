import pandas as pd, numpy as np
np.seterr(all='ignore')
df = pd.read_parquet('notebooks/data/dar_calibstars_dataset.parquet',
                     columns=['EXPID','X','Y','loss','airmass'])
pt = pd.read_csv('data/dar_exposure_pointing.csv', usecols=['EXPID','parallactic'])
df = df.merge(pt, on='EXPID', how='inner')
df = df[np.isfinite(df.loss) & np.isfinite(df.X)&np.isfinite(df.Y)&np.isfinite(df.parallactic)]
names=['rad','fdipx','fdipy','rdipx','rdipy','fq1','fq2','rq1','rq2']

def build(sub, qcol='parallactic'):
    Rn=410.0; u=sub.X.values/Rn; v=sub.Y.values/Rn
    q=np.deg2rad(sub[qcol].values); c,s=np.cos(q),np.sin(q)
    up=u*c+v*s; vp=-u*s+v*c
    M=np.column_stack([u*u+v*v,u,v,up,vp,u*u-v*v,2*u*v,up*up-vp*vp,2*up*vp])
    return M

def fit(sub, clip, qcol='parallactic'):
    sub=sub[sub.loss.between(-clip,clip)]
    M=build(sub,qcol); y=sub.loss.values.astype(float); e=sub.EXPID.values
    d=pd.DataFrame(M,columns=names); d['y']=y; d['e']=e
    gm=d.groupby('e')[names+['y']].transform('mean')
    Xd=(d[names]-gm[names]).values; yd=(d['y']-gm['y']).values
    beta=np.linalg.lstsq(Xd,yd,rcond=None)[0]
    dd=dict(zip(names,beta))
    Drot=np.hypot(dd['rdipx'],dd['rdipy']); Qrot=np.hypot(dd['rq1'],dd['rq2'])
    return Drot,Qrot

base=df[df.airmass>1.6]
print("(A) outlier sensitivity, airmass>1.6:")
for clip in [0.30,0.15,0.08]:
    Dr,Qr=fit(base,clip)
    print(f'   clip |loss|<{clip}: D_rot={Dr:.4f} Q_rot={Qr:.4f} D/Q={Dr/Qr:.2f}')

print("\n(B) q-permutation null (shuffle parallactic across exposures), airmass>1.6, clip 0.15:")
rng=np.random.default_rng(1)
sub=base[base.loss.between(-0.15,0.15)].copy()
# real
Dr,Qr=fit(base,0.15); print(f'   REAL:      D_rot={Dr:.4f}  Q_rot={Qr:.4f}')
# permuted: assign each exposure a random OTHER exposure's parallactic
exps=sub.EXPID.unique()
for t in range(3):
    perm=exps.copy(); rng.shuffle(perm)
    mp=dict(zip(exps,perm))
    fake_q=pt.set_index('EXPID').loc[[mp[x] for x in sub.EXPID.values],'parallactic'].values
    s2=sub.copy(); s2['parallactic']=fake_q
    Dr2,Qr2=fit(s2,0.15)
    print(f'   shuffled{t}: D_rot={Dr2:.4f}  Q_rot={Qr2:.4f}')

print("\n(C) rough absolute scale: implied delta0 in microns for a range of sigma_eff")
Dr,Qr=fit(base,0.15)
for sig in [35,50,70]:
    dG=sig*np.sqrt(2*Qr); d0=Dr*sig/np.sqrt(2*Qr)
    print(f'   sigma_eff={sig}um -> Delta_G(edge)={dG:.1f}um, delta0={d0:.1f}um  (D/Q={Dr/Qr:.2f})')
