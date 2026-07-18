from __future__ import annotations

import csv
import json
import math
import shutil
import statistics
import time
import zipfile
import re
from pathlib import Path

import numpy as np
from huggingface_hub import hf_hub_download, snapshot_download
from PIL import Image
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_fscore_support, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / 'weavevision_ci' / 'work_v08'
O = ROOT / 'weavevision_ci' / 'outputs_v08'
D = W / 'datasets'
DL = W / 'downloads'
EXT = {'.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp'}
CLAIM = 'OPEN_SOURCE_TEXTILE_PROXY_ONLY'


def log(message): print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)
def imgs(path): return sorted(p for p in path.rglob('*') if p.is_file() and p.suffix.lower() in EXT)
def rgb_image(path):
    with Image.open(path) as im: return im.convert('RGB').copy()
def rgb_array(image,size=128): return np.asarray(image.resize((size,size),Image.Resampling.BILINEAR),np.float32)/255.
def gray(a): return .299*a[...,0]+.587*a[...,1]+.114*a[...,2]
def grad(g):
    gx=np.zeros_like(g);gy=np.zeros_like(g);gx[:,1:-1]=(g[:,2:]-g[:,:-2])*.5;gy[1:-1]=(g[2:]-g[:-2])*.5
    return gx,gy,np.sqrt(gx*gx+gy*gy)
def hist(a,bins,lo,hi,w=None):
    h=np.histogram(a,bins,(lo,hi),weights=w)[0].astype(np.float32);return h/max(float(h.sum()),1e-6)
def blur(a,r):
    k=2*r+1;p=np.pad(a.astype(np.float32),((r,r),(r,r)),mode='edge');i=np.pad(p,((1,0),(1,0))).cumsum(0).cumsum(1)
    return (i[k:,k:]-i[:-k,k:]-i[k:,:-k]+i[:-k,:-k])/(k*k)
def robust(a):
    m=np.median(a,(0,1),keepdims=True);q10=np.percentile(a,10,(0,1),keepdims=True);q90=np.percentile(a,90,(0,1),keepdims=True)
    return np.clip((a-m)/np.maximum((q90-q10)/2.563,.025),-4,4).astype(np.float32)
def safe_rel(name,root):
    n=name.replace('\\','/');r=n[len(root.rstrip('/'))+1:]
    if '..' in Path(r).parts: raise RuntimeError('unsafe archive member')
    return r


def image_desc(image,size=96):
    a=rgb_array(image,size);g=gray(a);gx,gy,mag=grad(g);ori=(np.arctan2(gy,gx)+np.pi)/(2*np.pi);parts=[]
    for c in range(3):parts.append(hist(a[...,c],8,0,1))
    parts += [hist(g,12,0,1),hist(mag,10,0,.5),hist(ori,12,0,1,mag+1e-5)]
    z=g-g.mean();s=abs(np.fft.rfft2(z))**2;yy=np.fft.fftfreq(size)[:,None];xx=np.fft.rfftfreq(size)[None,:];rad=np.sqrt(xx*xx+yy*yy);t=max(float(s.sum()),1e-6);edges=np.linspace(0,.72,9)
    parts.append(np.array([s[(rad>=lo)&(rad<hi)].sum()/t for lo,hi in zip(edges[:-1],edges[1:])],np.float32))
    low=np.asarray(Image.fromarray(np.uint8(np.clip(g*255,0,255))).resize((8,8),Image.Resampling.BILINEAR),np.float32);low=(low-low.mean())/max(float(low.std()),1.)
    parts.append(low.ravel());return np.concatenate(parts).astype(np.float32)

def domain_blocks(image,size=96,grid=4):
    a=rgb_array(image,size);g=gray(a);gx,gy,mag=grad(g);ori=(np.arctan2(gy,gx)+np.pi)/(2*np.pi);b=size//grid;out=[]
    for r in range(grid):
      for c in range(grid):
        y1,y2=r*b,(r+1)*b;x1,x2=c*b,(c+1)*b;p=a[y1:y2,x1:x2];q=g[y1:y2,x1:x2];m=mag[y1:y2,x1:x2];o=ori[y1:y2,x1:x2]
        out.append(np.r_[p.mean((0,1)),p.std((0,1)),q.mean(),q.std(),m.mean(),m.std(),hist(q,6,0,1),hist(o,6,0,1,m+1e-5)])
    return np.asarray(out,np.float32)
def conformal(scores,alpha=.1):
    v=np.sort(np.asarray(scores,np.float32));k=math.ceil((len(v)+1)*(1-alpha));return float(v[min(max(k-1,0),len(v)-1)])
def nearest(q,m):
    return np.sqrt(np.maximum(np.sum(q*q)+np.sum(m*m,1)-2*m@q,0)).astype(np.float32)
def phase(ref,q,max_shift=10):
    r=ref-ref.mean();x=q-q.mean();c=np.fft.fft2(x)*np.conj(np.fft.fft2(r));c/=np.maximum(abs(c),1e-7);y,z=np.unravel_index(np.argmax(np.fft.ifft2(c).real),r.shape)
    y=y-r.shape[0] if y>r.shape[0]//2 else y;z=z-r.shape[1] if z>r.shape[1]//2 else z
    return int(np.clip(y,-max_shift,max_shift)),int(np.clip(z,-max_shift,max_shift))
def residual(q,ref):
    dy,dx=phase(gray(ref),gray(q));r=np.roll(ref,(dy,dx),(0,1))
    if dy>0:r[:dy]=q[:dy]
    elif dy<0:r[dy:]=q[dy:]
    if dx>0:r[:,:dx]=q[:,:dx]
    elif dx<0:r[:,dx:]=q[:,dx:]
    qn,rn=robust(q),robust(r);qg,rg=gray(qn),gray(rn);_,_,qm=grad(qg);_,_,rm=grad(rg)
    e=.25*np.mean(abs(qn-rn),2)+.5*abs((qg-blur(qg,3))-(rg-blur(rg,3)))+.25*abs(qm-rm)
    return blur(e,2)


class Model:
    def fit(self,paths):
        ims=[rgb_image(p) for p in paths];id0=np.stack([image_desc(i) for i in ims]);self.ic=np.median(id0,0);self.isc=np.maximum(1.4826*np.median(abs(id0-self.ic),0),.025);self.ids=(id0-self.ic)/self.isc
        bl=np.concatenate([domain_blocks(i) for i in ims]);self.dc=np.median(bl,0);self.ds=np.maximum(1.4826*np.median(abs(bl-self.dc),0),.035);self.dm=(bl-self.dc)/self.ds
        self.refs=np.stack([rgb_array(i) for i in ims]);return self
    def dscore(self,path):
        b=(domain_blocks(rgb_image(path))-self.dc)/self.ds;ms=np.sum(self.dm*self.dm,1)[None,:];sq=np.maximum(np.sum(b*b,1)[:,None]+ms-2*b@self.dm.T,0);return float(np.median(np.sqrt(sq.min(1))/np.sqrt(b.shape[1])))
    def rscore(self,path):
        im=rgb_image(path);q=rgb_array(im);d=nearest((image_desc(im)-self.ic)/self.isc,self.ids);idx=np.argpartition(d,min(2,len(d)-1))[:min(3,len(d))];h=np.min(np.stack([residual(q,self.refs[i]) for i in idx]),0);return float(np.quantile(h,.99)),h
    def calibrate(self,paths):
        ds=[self.dscore(p) for p in paths];rs=[self.rscore(p)[0] for p in paths];self.dt=conformal(ds,.1);self.rt=conformal(rs,.1);return self
    def save(self,path):np.savez_compressed(path,ic=self.ic,isc=self.isc,ids=self.ids,dc=self.dc,ds=self.ds,dm=self.dm,refs=self.refs,dt=self.dt,rt=self.rt)


def acquire_itd():
    z=Path(hf_hub_download(repo_id='SimTho/IndustrialTextileDataset',repo_type='dataset',filename='ITD.zip',local_dir=DL/'itd'));out=D/'itd';shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
    with zipfile.ZipFile(z) as q:
      names=q.namelist();roots={}
      for n in names:
        m=re.search(r'^(.*?)(type\d+cam\d+)/train/good/',n.replace('\\','/'))
        if m:roots[m.group(2)]=(m.group(1)+m.group(2)).strip('/')
      root=roots['type1cam1']
      for n in names:
        if n.replace('\\','/').startswith(root+'/') and not n.endswith('/'):
          t=out/'type1cam1'/safe_rel(n,root);t.parent.mkdir(parents=True,exist_ok=True)
          with q.open(n) as a,t.open('wb') as b:shutil.copyfileobj(a,b)
    return out/'type1cam1',{'dataset':'IndustrialTextileDataset/type1cam1','license':'MIT','archive_bytes':z.stat().st_size}
def acquire_mvtec():
    snap=Path(snapshot_download(repo_id='jiang-cc/MMAD',repo_type='dataset',revision='74db7cacf256eb62b5ce87094f83e9201fb7ac0a',allow_patterns=['MVTec-AD/carpet/**'],local_dir=DL/'mvtec'));root=snap/'MVTec-AD'/'carpet'
    return root,{'dataset':'MVTec-AD carpet','license_policy':'RESEARCH_ONLY_CC_BY_NC_SA_4_0','revision':'74db7cacf256eb62b5ce87094f83e9201fb7ac0a'}
def groups(root,limit=80):
    good=imgs(root/'test'/'good');bad=[]
    for p in sorted((root/'test').iterdir()):
      if p.is_dir() and p.name.lower() not in {'good','ground_truth','mask','masks'}:bad+=imgs(p)
    return good,sorted(bad)[:limit]
def binary_metrics(labels,scores,preds,latencies):
    y=np.array(labels);s=np.array(scores);z=np.array(preds);pr,re,f1,_=precision_recall_fscore_support(y,z,average='binary',zero_division=0);tn,fp,fn,tp=confusion_matrix(y,z,labels=[0,1]).ravel();ls=sorted(latencies)
    return {'roc_auc':round(float(roc_auc_score(y,s)),4),'average_precision':round(float(average_precision_score(y,s)),4),'precision':round(float(pr),4),'recall':round(float(re),4),'f1':round(float(f1),4),'fnr':round(float(fn/max(fn+tp,1)),4),'fpr':round(float(fp/max(fp+tn,1)),4),'cm':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)},'mean_latency_ms':round(statistics.mean(ls),3),'p95_latency_ms':round(ls[max(0,math.ceil(.95*len(ls))-1)],3)}


def main():
    for p in [W,O,D,DL]:p.mkdir(parents=True,exist_ok=True)
    itd,itdm=acquire_itd();mv,mvm=acquire_mvtec();train=imgs(mv/'train'/'good');fit,cal=train[:40],train[40:49];good,bad=groups(mv);mismatch=(imgs(itd/'test'/'good')+sum([imgs(p) for p in sorted((itd/'test').iterdir()) if p.is_dir() and p.name!='good'],[]))[:114]
    log(f'fit={len(fit)} cal={len(cal)} good={len(good)} defect={len(bad)} mismatch={len(mismatch)}')
    model=Model().fit(fit).calibrate(cal);model.save(O/'domain_residual_model.npz')
    d_good=[model.dscore(p) for p in good];d_bad=[model.dscore(p) for p in bad];d_mis=[model.dscore(p) for p in mismatch]
    domain_labels=[0]*(len(d_good)+len(d_bad))+[1]*len(d_mis);domain_scores=d_good+d_bad+d_mis;domain_preds=[int(x>model.dt) for x in domain_scores]
    domain={'threshold':model.dt,'mismatch_recall':round(sum(x>model.dt for x in d_mis)/len(d_mis),4),'compatible_good_false_abstain':round(sum(x>model.dt for x in d_good)/len(d_good),4),'compatible_defect_abstain':round(sum(x>model.dt for x in d_bad)/len(d_bad),4),'roc_auc':round(float(roc_auc_score(domain_labels,domain_scores)),4),'cm':dict(zip(['tn','fp','fn','tp'],map(int,confusion_matrix(domain_labels,domain_preds,labels=[0,1]).ravel())))}
    rows=[];labels=[];scores=[];preds=[];lats=[];states={'NORMAL':0,'REVIEW':0,'ABSTAIN_DOMAIN_MISMATCH':0}
    for y,paths in [(0,good),(1,bad)]:
      for p in paths:
        t=time.perf_counter();ds=model.dscore(p);rs,_=model.rscore(p);lat=(time.perf_counter()-t)*1000;pred=int(rs>model.rt+1e-8);state='ABSTAIN_DOMAIN_MISMATCH' if ds>model.dt else 'REVIEW' if pred else 'NORMAL';states[state]+=1
        labels.append(y);scores.append(rs);preds.append(pred);lats.append(lat);rows.append({'path':str(p),'label':y,'domain_score':ds,'domain_threshold':model.dt,'residual_score':rs,'residual_threshold':model.rt,'residual_predicted':pred,'state':state,'latency_ms':lat})
    residual_metrics=binary_metrics(labels,scores,preds,lats);residual_metrics['threshold']=model.rt
    criteria={'mismatch_recall_min':.95,'compatible_good_false_abstain_max':.10,'residual_roc_auc_min':.80,'fnr_max':.20,'fpr_max':.20,'p95_latency_ms_max':250}
    checks={'mismatch_recall':domain['mismatch_recall']>=.95,'false_abstain':domain['compatible_good_false_abstain']<=.10,'residual_auc':residual_metrics['roc_auc']>=.80,'fnr':residual_metrics['fnr']<=.20,'fpr':residual_metrics['fpr']<=.20,'latency':residual_metrics['p95_latency_ms']<=250};verdict='PASS' if all(checks.values()) else 'PASS_WITH_RESTRICTIONS' if checks['mismatch_recall'] and checks['false_abstain'] else 'FAIL_DOMAIN_GATE'
    report={'release':'v0.8.0a1','claim':CLAIM,'verdict':verdict,'source':itdm,'family':mvm,'split_counts':{'fit':len(fit),'calibration':len(cal),'test_good':len(good),'test_defect':len(bad),'mismatch':len(mismatch)},'threshold_protocol':'split_conformal_alpha_0.10','domain':domain,'residual':residual_metrics,'states':states,'criteria':criteria,'checks':checks,'production_deployment':'BLOCKED'}
    (O/'domain_residual_experiment.json').write_text(json.dumps(report,indent=2));
    with (O/'domain_residual_predictions.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    summary=['# WeaveVision v0.8.0a1','',f'Verdict: **{verdict}**','',f"- Mismatch recall: {domain['mismatch_recall']}",f"- Compatible-good false abstain: {domain['compatible_good_false_abstain']}",f"- Compatible-defect abstain: {domain['compatible_defect_abstain']}",f"- Residual AUROC: {residual_metrics['roc_auc']}",f"- Residual FNR: {residual_metrics['fnr']}",f"- Residual FPR: {residual_metrics['fpr']}",f"- P95 latency: {residual_metrics['p95_latency_ms']} ms",'',f'Checks: `{checks}`','',f'Claim: `{CLAIM}`. Not company validation.']
    (O/'DOMAIN_RESIDUAL_SUMMARY.md').write_text('\n'.join(summary))
    html='<html><meta charset=utf-8><style>body{font-family:Arial;max-width:1000px;margin:auto}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:7px}</style><h1>WeaveVision v0.8.0a1</h1><b>'+verdict+'</b><h2>Domain</h2><pre>'+json.dumps(domain,indent=2)+'</pre><h2>Residual</h2><pre>'+json.dumps(residual_metrics,indent=2)+'</pre><h2>Checks</h2><pre>'+json.dumps(checks,indent=2)+'</pre><p>'+CLAIM+'; not company validation.</p></html>'
    (O/'domain_residual_report.html').write_text(html)
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
