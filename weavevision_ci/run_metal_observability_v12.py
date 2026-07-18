from __future__ import annotations
import csv, html, json, math, statistics, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
import run_domain_residual_v08 as base

ROOT=Path(__file__).resolve().parents[1]; O=ROOT/'weavevision_ci'/'outputs_v12'; CLAIM='OPEN_SOURCE_TEXTILE_PROXY_ONLY'
NAMES=('neutral_bright_fraction','neutral_dark_fraction','achromatic_extreme_fraction','neutral_residual_q99','neutral_edge_coincidence','bright_tophat_q99','dark_bottomhat_q99','chroma_suppression_q99','neutral_component_fraction','neutral_component_peak','local_highpass_excess_q99','dual_polarity_support')
PERT=('identity','brightness_0.90','brightness_1.10','gamma_0.90','gamma_1.10','blur_0.6')

def chroma(a): return np.max(a,2)-np.min(a,2)
def gradient(g):
    gx=np.zeros_like(g);gy=np.zeros_like(g);gx[:,1:-1]=.5*(g[:,2:]-g[:,:-2]);gy[1:-1]=.5*(g[2:]-g[:-2]);return np.sqrt(gx*gx+gy*gy)
def pmatch(r,q):
    out=np.empty_like(r)
    for c in range(3):
        a=r[...,c];b=q[...,c];am=float(np.median(a));bm=float(np.median(b));ai=max(float(np.percentile(a,90)-np.percentile(a,10)),.04);bi=max(float(np.percentile(b,90)-np.percentile(b,10)),.04);out[...,c]=(a-am)*(bi/ai)+bm
    return np.clip(out,0,1).astype(np.float32)
def align(r,q):
    dy,dx=base.phase(base.gray(r),base.gray(q));a=np.roll(r,(dy,dx),(0,1))
    if dy>0:a[:dy]=q[:dy]
    elif dy<0:a[dy:]=q[dy:]
    if dx>0:a[:,:dx]=q[:,:dx]
    elif dx<0:a[:,dx:]=q[:,dx:]
    return a
def largest(mask,w):
    h,ww=mask.shape;seen=np.zeros_like(mask,bool);best=0;peak=0.
    for y in range(h):
      for x in range(ww):
       if mask[y,x] and not seen[y,x]:
        st=[(y,x)];seen[y,x]=1;n=0;p=0.
        while st:
         yy,xx=st.pop();n+=1;p=max(p,float(w[yy,xx]))
         for ny,nx in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
          if 0<=ny<h and 0<=nx<ww and mask[ny,nx] and not seen[ny,nx]:seen[ny,nx]=1;st.append((ny,nx))
        if n>best:best=n;peak=p
    return best/(h*ww),peak
def one(q,r):
    r=pmatch(align(r,q),q);qg=base.gray(q);rg=base.gray(r);d=qg-rg;ad=abs(d);qc=chroma(q);rc=chroma(r);nw=np.clip(1-qc/.18,0,1);neutral=qc<=.12;br=neutral&(d>=.12);dk=neutral&(d<=-.12);ex=br|dk;gr=gradient(qg);lm=base.blur(qg,3);bt=np.maximum(qg-lm,0)*nw;db=np.maximum(lm-qg,0)*nw;hq=abs(qg-base.blur(qg,2));hr=abs(rg-base.blur(rg,2));hp=np.maximum(hq-hr,0);cs=np.maximum(rc-qc,0)*ad;cf,cp=largest(ex,ad);ec=float(np.percentile(gr[ex],95)) if ex.any() else 0.;bf=float(br.mean());df=float(dk.mean())
    return np.array([bf,df,float(ex.mean()),float(np.quantile(ad*nw,.99)),ec,float(np.quantile(bt,.99)),float(np.quantile(db,.99)),float(np.quantile(cs,.99)),cf,cp,float(np.quantile(hp,.99)),float(np.sqrt(bf*df))],np.float32)
def norm_desc(ims):
    d=np.stack([base.image_desc(i) for i in ims]);c=np.median(d,0);s=np.maximum(1.4826*np.median(abs(d-c),0),.025);return c,s,(d-c)/s
def idx(image,c,s,m,k):
    q=(base.image_desc(image)-c)/s;d=base.nearest(q,m);n=min(k,len(d));return np.argpartition(d,n-1)[:n]
def comp(z): return float(max(max(z[0],z[4],z[5],z[7]),max(z[1],z[6],z[8],z[9],z[10]),z[2],z[3],z[11]))
class Memory:
    pass
def fit_memory(fit,cal):
    m=Memory();m.c,m.s,m.d=norm_desc(fit);m.refs=np.stack([base.rgb_array(i) for i in fit]);loo=[]
    for i,im in enumerate(fit):
      keep=np.arange(len(fit))!=i;q=base.rgb_array(im);qd=(base.image_desc(im)-m.c)/m.s;dist=base.nearest(qd,m.d[keep]);available=np.arange(len(fit))[keep];n=min(3,len(dist));sel=available[np.argpartition(dist,n-1)[:n]];loo.append(np.min(np.stack([one(q,m.refs[j]) for j in sel]),0))
    raw=np.stack(loo);m.oc=np.median(raw,0);m.os=np.maximum(1.4826*np.median(abs(raw-m.oc),0),1e-4)
    cs=[score(im,m)[0] for im in cal];m.cal=np.array(cs);m.th=base.conformal(m.cal,.1);return m
def score(im,m):
    q=base.rgb_array(im);sel=idx(im,m.c,m.s,m.d,3);raw=np.min(np.stack([one(q,m.refs[j]) for j in sel]),0);z=(raw-m.oc)/m.os;return comp(z),raw,z
def perturb(im,name):
    if name=='identity':return im.copy()
    if name=='blur_0.6':return im.filter(ImageFilter.GaussianBlur(.6))
    a=np.asarray(im,np.float32)/255
    if name=='brightness_0.90':a=np.clip(a*.9,0,1)
    elif name=='brightness_1.10':a=np.clip(a*1.1,0,1)
    elif name=='gamma_0.90':a=np.clip(a,0,1)**.9
    elif name=='gamma_1.10':a=np.clip(a,0,1)**1.1
    return Image.fromarray(np.uint8(a*255))
def boot(n,m,it=2000):
    n=np.array(n);m=np.array(m);rng=np.random.default_rng(20260718);y=np.r_[np.zeros(len(n)),np.ones(len(m))];v=[]
    for _ in range(it):v.append(roc_auc_score(y,np.r_[n[rng.integers(0,len(n),len(n))],m[rng.integers(0,len(m),len(m))]]))
    return float(np.quantile(v,.025)),float(np.quantile(v,.975))
def perm(y,x,it=5000):
    y=np.array(y);x=np.asarray(x);obs=np.array([roc_auc_score(y,x[:,j]) for j in range(x.shape[1])]);rng=np.random.default_rng(20260718);raw=np.zeros(x.shape[1],int);mx=np.zeros(x.shape[1],int)
    for _ in range(it):
      yp=rng.permutation(y);a=np.array([roc_auc_score(yp,x[:,j]) for j in range(x.shape[1])]);raw+=a>=obs;maximum=a.max();mx+=maximum>=obs
    return (raw+1)/(it+1),(mx+1)/(it+1)
def metrics(y,s,th,l):
    y=np.array(y);s=np.array(s);z=(s>th).astype(int);tn,fp,fn,tp=confusion_matrix(y,z,labels=[0,1]).ravel();ls=sorted(l);return {'roc_auc':float(roc_auc_score(y,s)),'average_precision':float(average_precision_score(y,s)),'precision':tp/max(tp+fp,1),'recall':tp/max(tp+fn,1),'fnr':fn/max(fn+tp,1),'fpr':fp/max(fp+tn,1),'cm':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)},'mean_latency_ms':statistics.mean(ls),'p95_latency_ms':ls[max(0,math.ceil(.95*len(ls))-1)],'threshold':float(th)}
def overlap(a,b):
    c=np.array(a+b);lo,hi=c.min(),c.max()
    if hi<=lo:return 1.
    x,e=np.histogram(a,20,(lo,hi),density=True);y,_=np.histogram(b,e,density=True);return float(np.sum(np.minimum(x,y)*np.diff(e)))
def csvout(p,rows):
    with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    O.mkdir(parents=True,exist_ok=True);_,_=base.acquire_itd();mv,mvm=base.acquire_mvtec();train=base.imgs(mv/'train'/'good');fit=[base.rgb_image(p) for p in train[:40]];cal=[base.rgb_image(p) for p in train[40:49]];good=base.imgs(mv/'test'/'good');metal=base.imgs(mv/'test'/'metal_contamination');base.log(f'fit={len(fit)} cal={len(cal)} good={len(good)} metal={len(metal)}');m=fit_memory(fit,cal);entries=[(0,'good',p) for p in good]+[(1,'metal_contamination',p) for p in metal];rows=[];y=[];scores=[];zs=[];lats=[]
    for label,group,p in entries:
      st=time.perf_counter();sc,raw,z=score(base.rgb_image(p),m);lat=(time.perf_counter()-st)*1000;r={'path':str(p),'label':label,'subgroup':group,'composite_score':sc,'threshold':m.th,'predicted':int(sc>m.th),'latency_ms':lat};r.update({f'raw_{n}':float(raw[i]) for i,n in enumerate(NAMES)});r.update({f'z_{n}':float(z[i]) for i,n in enumerate(NAMES)});rows.append(r);y.append(label);scores.append(sc);zs.append(z);lats.append(lat)
    met=metrics(y,scores,m.th,lats);ns=[r['composite_score'] for r in rows if r['label']==0];ms=[r['composite_score'] for r in rows if r['label']==1];lo,hi=boot(ns,ms);primary_p=perm(y,np.array(scores)[:,None])[0][0];rawp,corr=perm(y,np.stack(zs));obs=[]
    for i,n in enumerate(NAMES):
      a=float(roc_auc_score(y,np.stack(zs)[:,i]));obs.append({'observable':n,'roc_auc':a,'raw_permutation_p':float(rawp[i]),'max_stat_corrected_p':float(corr[i]),'normal_median':float(np.median(np.stack(zs)[np.array(y)==0,i])),'metal_median':float(np.median(np.stack(zs)[np.array(y)==1,i]))})
    rob=[]
    for name in PERT:
      ss=[];ll=[]
      for label,_,p in entries:
       im=perturb(base.rgb_image(p),name);st=time.perf_counter();sc,_,_=score(im,m);ll.append((time.perf_counter()-st)*1000);ss.append(sc)
      z=metrics(y,ss,m.th,ll);rob.append({'perturbation':name,'roc_auc':z['roc_auc'],'recall':z['recall'],'fpr':z['fpr'],'p95_latency_ms':z['p95_latency_ms']})
    worst_r=min(x['recall'] for x in rob);worst_f=max(x['fpr'] for x in rob);checks={'auc':met['roc_auc']>=.8,'bootstrap_lower':lo>=.65,'recall':met['recall']>=.8,'fpr':met['fpr']<=.2,'permutation':primary_p<=.05,'robust_recall':worst_r>=.7,'robust_fpr':worst_f<=.3,'latency':met['p95_latency_ms']<=250};operational=all(checks.values());candidate=any(x['roc_auc']>=.7 and x['max_stat_corrected_p']<=.05 for x in obs);weak=met['roc_auc']>=.65 or candidate or lo>.5
    if operational:v='PASS_UNUSED_RGB_OBSERVABLE'
    elif met['roc_auc']>=.8 and met['recall']>=.8 and met['fpr']<=.2 and lo<.65:v='INCONCLUSIVE_SAMPLE_LIMITED'
    elif weak:v='PASS_WEAK_UNUSED_RGB_SIGNAL'
    else:v='RGB_CAPTURE_INSUFFICIENT_FOR_FROZEN_OBSERVABLES'
    report={'release':'v0.12.0a1','claim':CLAIM,'verdict':v,'integrity':{'r1_frozen':True,'weak_local_threshold_changed':False,'new_classifier':False,'metal_label_feature_selection':False,'metal_label_threshold_tuning':False},'family':mvm,'split_counts':{'fit_good':40,'calibration_good':9,'test_good':len(good),'test_metal':len(metal)},'primary_composite':{**met,'bootstrap_auc_95_ci':[lo,hi],'permutation_p':float(primary_p),'score_overlap':overlap(ns,ms)},'operational_checks':checks,'capture_robustness':{'worst_recall':worst_r,'worst_fpr':worst_f,'gate':worst_r>=.7 and worst_f<=.3},'corrected_observable_candidate':candidate,'authorization':{'unused_rgb_observable_contract':v=='PASS_UNUSED_RGB_OBSERVABLE','metal_detector':False,'production_deployment':False}}
    (O/'metal_observability_audit.json').write_text(json.dumps(report,indent=2));csvout(O/'metal_observables.csv',rows);csvout(O/'observable_statistics.csv',obs);csvout(O/'perturbation_robustness.csv',rob)
    def tab(d):return ''.join(f'<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(vv))}</td></tr>' for k,vv in d.items())
    page=f"<html><meta charset=utf-8><style>body{{font-family:Arial;max-width:1200px;margin:auto}}table{{border-collapse:collapse}}th,td{{border:1px solid #ccc;padding:7px}}</style><h1>WeaveVision v0.12 Metal Observability</h1><b>{v}</b><h2>Primary</h2><table>{tab(report['primary_composite'])}</table><h2>Checks</h2><table>{tab(checks)}</table></html>";(O/'metal_observability_report.html').write_text(page);(O/'METAL_OBSERVABILITY_SUMMARY.md').write_text(f'# WeaveVision v0.12.0a1\n\nVerdict: **{v}**\n\n```json\n{json.dumps(report,indent=2)}\n```\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
