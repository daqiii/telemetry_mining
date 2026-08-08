import pandas as pd, numpy as np
np.seterr(all='ignore')

df = pd.read_parquet('/Users/klaus/telemetry_mining-trunk/notebooks/data/dar_calibstars_dataset.parquet',
                     columns=['EXPID','X','Y','loss','airmass'])
pt = pd.read_csv('/Users/klaus/telemetry_mining-trunk/data/dar_exposure_pointing.csv',
                 usecols=['EXPID','parallactic'])
df=df.merge(pt,on='EXPID',how='inner')
df=df[np.isfinite(df.loss)&df.loss.between(-0.3,0.3)&np.isfinite(df.X)&np.isfinite(df.Y)&np.isfinite(df.parallactic)]
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
    return np.hypot(dd['rdipx'],dd['rdipy']), np.hypot(dd['rq1'],dd['rq2'])

SIG=52.0      # sigma_eff, um (real FastFiberAcceptance)
PLATE=71.0    # um/arcsec (edge ~73, mid ~70)
print("Convert measured rotating quadrupole Q_rot to a physical EDGE offset:")
print("  DeltaG_edge = sigma_eff * sqrt(2*Q_rot)   [characteristic amplitude; instantaneous model]")
print(f"  (sigma_eff={SIG}um, plate~{PLATE}um/arcsec)\n")
print(f"{'airmass bin':<14}{'mean_am':>8}{'n_exp':>7}{'D_rot':>8}{'Q_rot':>8}{'DeltaG(um)':>11}{'DeltaG(\")':>10}{'D_rot/Q':>9}")
for lo,hi in [(1.4,1.6),(1.6,1.8),(1.8,2.05),(1.4,2.05)]:
    sub=df[(df.airmass>=lo)&(df.airmass<hi)]
    Dr,Qr=fit(sub)
    dG=SIG*np.sqrt(2*Qr)
    tag=f"{lo}-{hi}"
    print(f"{tag:<14}{sub.airmass.mean():>8.2f}{sub.EXPID.nunique():>7}{Dr:>8.4f}{Qr:>8.4f}{dG:>11.1f}{dG/PLATE:>10.3f}{Dr/Qr:>9.2f}")

print("\n--- reference numbers from the other analyses (at airmass ~2) ---")
print("  Weiner DESI-9817:  intra-exposure image motion at field edge ~ 0.25\" (~18 um) at elev 30 (X=2)")
print("  Kirkby DESI-8586:  sky moves ~15 um (~0.21\") over 1000s at X=2 (quadrupole = irreducible residual)")
print("\n  Note: our DeltaG carries ~factor-2 total uncertainty (sigma_eff + a ~sqrt(3) time-averaging")
print("  factor between the loss-integrated RMS offset and their peak edge motion). D_rot/Q_rot~1.9 is the")
print("  robust, conversion-free number: the dipole is ~2x the quadrupole.")
