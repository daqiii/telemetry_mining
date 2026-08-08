import pandas as pd, numpy as np
np.seterr(all='ignore')

df = pd.read_parquet('notebooks/data/dar_calibstars_dataset.parquet',
                     columns=['EXPID','X','Y','loss','airmass'])
pt = pd.read_csv('data/dar_exposure_pointing.csv', usecols=['EXPID','parallactic'])
df = df.merge(pt, on='EXPID', how='inner')
df = df[np.isfinite(df.loss) & df.loss.between(-0.3,0.3) &
        np.isfinite(df.X) & np.isfinite(df.Y) & np.isfinite(df.parallactic)]
Rn=410.0
u=df.X.values/Rn; v=df.Y.values/Rn
q=np.deg2rad(df.parallactic.values)
c,s=np.cos(q),np.sin(q)
up= u*c+v*s; vp=-u*s+v*c
cols = {
 'rad':u*u+v*v,
 'fdipx':u,'fdipy':v,
 'rdipx':up,'rdipy':vp,
 'fq1':u*u-v*v,'fq2':2*u*v,
 'rq1':up*up-vp*vp,'rq2':2*up*vp,
}
names=list(cols); M=np.column_stack([cols[k] for k in names])
y=df.loss.values.astype(float)
eid=df.EXPID.values
am=df.airmass.values

def within_demean(M,y,eid,mask):
    Mm=M[mask]; ym=y[mask]; e=eid[mask]
    dfm=pd.DataFrame(Mm,columns=names); dfm['y']=ym; dfm['e']=e
    gm=dfm.groupby('e')[names+['y']].transform('mean')
    Xd=(dfm[names]-gm[names]).values
    yd=(dfm['y']-gm['y']).values
    return Xd,yd,e

def per_exp_normal(Xd,yd,e):
    # accumulate XtX, Xty per exposure for fast block bootstrap
    order=np.argsort(e,kind='stable')
    Xd=Xd[order]; yd=yd[order]; e=e[order]
    uniq,start=np.unique(e,return_index=True)
    ends=np.r_[start[1:],len(e)]
    XtX=np.empty((len(uniq),M.shape[1],M.shape[1]))
    Xty=np.empty((len(uniq),M.shape[1]))
    yty=np.empty(len(uniq))
    for i,(a,b) in enumerate(zip(start,ends)):
        Xi=Xd[a:b]; yi=yd[a:b]
        XtX[i]=Xi.T@Xi; Xty[i]=Xi.T@yi; yty[i]=yi@yi
    return XtX,Xty,yty,uniq

def solve(XtX,Xty):
    A=XtX.sum(0); b=Xty.sum(0)
    beta=np.linalg.solve(A,b)
    return beta
def amps(beta):
    d=dict(zip(names,beta))
    return (np.hypot(d['rdipx'],d['rdipy']), np.hypot(d['rq1'],d['rq2']),
            np.hypot(d['fdipx'],d['fdipy']), np.hypot(d['fq1'],d['fq2']))

for lo in [1.4,1.6,1.8]:
    mask=am>lo
    Xd,yd,e=within_demean(M,y,eid,mask)
    XtX,Xty,yty,uniq=per_exp_normal(Xd,yd,e)
    beta=solve(XtX,Xty)
    Drot,Qrot,Dfix,Qfix=amps(beta)
    ss_tot=yty.sum(); A=XtX.sum(0); b=Xty.sum(0)
    ss_res=ss_tot-beta@b; r2=1-ss_res/ss_tot
    # bootstrap over exposures
    rng=np.random.default_rng(0); ratios=[]; Ds=[];Qs=[]
    n=len(uniq)
    for _ in range(300):
        idx=rng.integers(0,n,n)
        bt=solve(XtX[idx],Xty[idx])
        dr,qr,_,_=amps(bt); ratios.append(dr/qr); Ds.append(dr); Qs.append(qr)
    ratios=np.array(ratios)
    lo_,med,hi=np.percentile(ratios,[16,50,84])
    print(f'airmass>{lo}: n_exp={n} n_star={mask.sum()}  R2={r2:.3f}')
    print(f'   D_rot={Drot:.4f}  Q_rot={Qrot:.4f}  D_fix={Dfix:.4f}  Q_fix={Qfix:.4f}')
    print(f'   D_rot/Q_rot = {Drot/Qrot:.2f}  [16-84%: {lo_:.2f}, {hi:.2f}]')
    print()
