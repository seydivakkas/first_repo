from __future__ import annotations
import csv,json,math,statistics,time,zipfile,re,shutil
from pathlib import Path
import numpy as np
from huggingface_hub import hf_hub_download,snapshot_download
from PIL import Image
from sklearn.metrics import average_precision_score,confusion_matrix,precision_recall_fscore_support,roc_auc_score

ROOT=Path(__file__).resolve().parents[1]; W=ROOT/'weavevision_ci'/'work_norm'; O=ROOT/'weavevision_ci'/'outputs_norm'; D=W/'datasets'; DL=W/'downloads'
EXT={'.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp'}; CLAIM='OPEN_SOURCE_TEXTILE_PROXY_ONLY'; Q=.95

def log(x): print(f'[{time.strftime("%H:%M:%S")}] {x}',flush=True)
def imgs(p): return sorted(x for x in p.rglob('*') if x.is_file() and x.suffix.lower() in EXT)
def rgb(p):
    with Image.open(p) as im:return im.convert('RGB').copy()
def safe_rel(n,root):
    n=n.replace('\\','/');r=n[len(root.rstrip('/'))+1:]
    if '..' in Path(r).parts:raise RuntimeError('unsafe member')
    return r

def acquire_itd():
    z=Path(hf_hub_download(repo_id='SimTho/IndustrialTextileDataset',repo_type='dataset',filename='ITD.zip',local_dir=DL/'itd'))
    out=D/'itd';marker=out/'.done.json'
    if marker.exists():return json.loads(marker.read_text())
    shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
    with zipfile.ZipFile(z) as q:
        names=q.namelist();roots={}
        for n in names:
            m=re.search(r'^(.*?)(type\d+cam\d+)/train/good/',n.replace('\\','/'))
            if m:roots[m.group(2)]=(m.group(1)+m.group(2)).strip('/')
        cat='type1cam1';root=roots[cat]
        for n in names:
            if n.replace('\\','/').startswith(root+'/') and not n.endswith('/'):
                t=out/cat/safe_rel(n,root);t.parent.mkdir(parents=True,exist_ok=True)
                with q.open(n) as a,t.open('wb') as b:shutil.copyfileobj(a,b)
    p={'dataset':'IndustrialTextileDataset','category':cat,'root':str(out/cat),'archive_bytes':z.stat().st_size,'license':'MIT'};marker.write_text(json.dumps(p,indent=2));return p

def acquire_mvtec():
    target=D/'mvtec_carpet';marker=target/'.done.json'
    if marker.exists():return json.loads(marker.read_text())
    snap=Path(snapshot_download(repo_id='jiang-cc/MMAD',repo_type='dataset',revision='74db7cacf256eb62b5ce87094f83e9201fb7ac0a',allow_patterns=['MVTec-AD/carpet/**'],local_dir=DL/'mvtec'))
    source=snap/'MVTec-AD'/'carpet'
    if not (source/'train'/'good').exists():raise RuntimeError(f'MVTec carpet train/good missing: {list(source.rglob("*"))[:20]}')
    shutil.rmtree(target,ignore_errors=True);shutil.copytree(source,target)
    p={'dataset':'MVTec-AD carpet','root':str(target),'license_policy':'RESEARCH_ONLY_CC_BY_NC_SA_4_0','train_good':len(imgs(target/'train'/'good')),'test_good':len(imgs(target/'test'/'good'))};marker.write_text(json.dumps(p,indent=2));return p

def resize(im,size=128):return np.asarray(im.resize((size,size),Image.Resampling.BILINEAR),np.float32)/255.
def grad(g):
    gx=np.zeros_like(g);gy=np.zeros_like(g);gx[:,1:-1]=(g[:,2:]-g[:,:-2])*.5;gy[1:-1]=(g[2:]-g[:-2])*.5;mag=np.sqrt(gx*gx+gy*gy);ori=(np.arctan2(gy,gx)+np.pi)/(2*np.pi);return gx,gy,mag,ori
def hist(a,bins,lo,hi,w=None):
    h=np.histogram(a,bins,(lo,hi),weights=w)[0].astype(np.float32);return h/max(float(h.sum()),1e-6)
def robust(a):
    med=np.median(a,(0,1),keepdims=True);q10=np.percentile(a,10,(0,1),keepdims=True);q90=np.percentile(a,90,(0,1),keepdims=True);s=np.maximum((q90-q10)/2.563,.025);return (np.clip((a-med)/s,-3,3)+3)/6
def lbp(g):
    c=g[1:-1,1:-1];ns=[g[:-2,:-2],g[:-2,1:-1],g[:-2,2:],g[1:-1,2:],g[2:,2:],g[2:,1:-1],g[2:,:-2],g[1:-1,:-2]];bits=np.stack([(n>=c).astype(np.uint8) for n in ns]);tr=np.sum(bits!=np.roll(bits,1,0),0);code=np.where(tr<=2,bits.sum(0),9);return hist(code,10,0,10)
def offsets(g):
    vals=[];c=g-g.mean();v=np.mean(c*c)+1e-6
    for dy,dx in [(0,1),(1,0),(0,2),(2,0),(1,1),(1,-1)]:
        if dx>0:a=g[dy:, :-dx];b=g[:-dy or None,dx:];ca=c[dy:,:-dx];cb=c[:-dy or None,dx:]
        else:a=g[dy:,-dx:];b=g[:-dy or None,:dx];ca=c[dy:,-dx:];cb=c[:-dy or None,:dx]
        vals += [float(np.mean(abs(a-b))),float(np.mean(ca*cb)/v)]
    return np.array(vals,np.float32)
def freq(g):
    s=abs(np.fft.rfft2(g-g.mean()))**2;yy=np.fft.fftfreq(g.shape[0])[:,None];xx=np.fft.rfftfreq(g.shape[1])[None,:];r=np.sqrt(xx*xx+yy*yy);t=max(float(s.sum()),1e-6);return np.array([s[(r>=a)&(r<b)].sum()/t for a,b in [(0,.12),(.12,.25),(.25,.5),(.5,.75)]],np.float32)
def features(im,mode):
    a=resize(im);a=robust(a) if mode=='robust' else a;g=a.mean(2);gx,gy,mag,ori=grad(g);tile=24 if mode=='self' else 16;stride=8;fs=[]
    for y in range(0,128-tile+1,stride):
      for x in range(0,128-tile+1,stride):
        q=g[y:y+tile,x:x+tile];m=mag[y:y+tile,x:x+tile]
        if mode=='self':f=np.r_[q.std(),np.percentile(q,10),np.percentile(q,90),m.mean(),m.std(),np.mean(abs(gx[y:y+tile,x:x+tile])),np.mean(abs(gy[y:y+tile,x:x+tile])),hist(ori[y:y+tile,x:x+tile],8,0,1,m+1e-5),lbp(q),offsets(q),freq(q)]
        else:
            p=a[y:y+tile,x:x+tile];f=np.r_[p.mean((0,1)),p.std((0,1)),q.mean(),q.std(),np.percentile(q,10),np.percentile(q,90),m.mean(),m.std(),hist(q,8,0,1)]
        fs.append(f.astype(np.float32))
    w=(128-tile)//stride+1;return np.stack(fs),w

def nearest(q,m):
    out=np.empty(len(q),np.float32);ms=np.sum(m*m,1)[None,:]
    for i in range(0,len(q),256):
        x=q[i:i+256];out[i:i+len(x)]=np.sqrt(np.maximum(np.sum(x*x,1)[:,None]+ms-2*x@m.T,0)).min(1)
    return out
class Model:
    def __init__(self,mode):self.mode=mode
    def fit(self,ps):
        x=np.concatenate([features(rgb(p),self.mode)[0] for p in ps]);self.c=np.median(x,0);self.s=np.maximum(1.4826*np.median(abs(x-self.c),0),.02);x=(x-self.c)/self.s;r=np.random.default_rng(42);self.m=x[r.choice(len(x),min(4096,len(x)),False)];return self
    def score(self,p):
        x,w=features(rgb(p),self.mode);d=nearest((x-self.c)/self.s,self.m);return float(np.percentile(d,95)),d.reshape(w,w)
    def calibrate(self,ps):
        s=np.array([self.score(p)[0] for p in ps]);self.th=float(np.quantile(s,Q));self.ss=max(float(np.median(abs(s-np.median(s)))*1.4826),self.th*.08,.03);return self
    def predict(self,p):
        t=time.perf_counter();s,h=self.score(p);return s,int(s>=self.th),1000*(time.perf_counter()-t),h

def groups(root,limit=80):
    good=imgs(root/'test'/'good');bad=[]
    for d in sorted((root/'test').iterdir()):
        if d.is_dir() and d.name.lower() not in {'good','ground_truth','mask','masks'}:bad+=imgs(d)
    return good,sorted(bad)[:limit]
def evaluate(m,root,dataset,method):
    good,bad=groups(root);rows=[]
    for y,ps in [(0,good),(1,bad)]:
      for p in ps:
        s,z,l,_=m.predict(p);rows.append({'method':method,'dataset':dataset,'path':str(p),'label':y,'score':s,'predicted':z,'latency_ms':l})
    y=np.array([r['label'] for r in rows]);s=np.array([r['score'] for r in rows]);z=np.array([r['predicted'] for r in rows]);pr,re,f1,_=precision_recall_fscore_support(y,z,average='binary',zero_division=0);tn,fp,fn,tp=confusion_matrix(y,z,labels=[0,1]).ravel();ls=sorted(r['latency_ms'] for r in rows)
    met={'good':len(good),'defect':len(bad),'roc_auc':round(float(roc_auc_score(y,s)),4),'average_precision':round(float(average_precision_score(y,s)),4),'precision':round(float(pr),4),'recall':round(float(re),4),'f1':round(float(f1),4),'fnr':round(float(fn/max(fn+tp,1)),4),'fpr':round(float(fp/max(fp+tn,1)),4),'cm':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)},'mean_latency_ms':round(statistics.mean(ls),3),'p95_latency_ms':round(ls[max(0,math.ceil(.95*len(ls))-1)],3),'threshold':round(m.th,6)};return met,rows
def gate(x):return x['roc_auc']>=.8 and x['fnr']<=.2 and x['fpr']<=.2 and x['p95_latency_ms']<=250

def main():
    for p in [W,O,D,DL]:p.mkdir(parents=True,exist_ok=True)
    itd=acquire_itd();mv=acquire_mvtec();ir=Path(itd['root']);er=Path(mv['root']);it=imgs(ir/'train'/'good');et=imgs(er/'train'/'good');sf,sc=it[:180],it[180:208];external_cal=max(8,min(28,len(et)//5));ef,ec=et[:-external_cal],et[-external_cal:]
    if len(sf)<180 or len(sc)<28 or len(ef)<20 or len(ec)<8:raise RuntimeError(f'insufficient normal split: {len(sf),len(sc),len(ef),len(ec)}')
    specs=[('M0_raw_source_frozen','raw',False),('M1_robust_appearance_source_frozen','robust',False),('M2_self_similarity_source_frozen','self',False),('M3_pattern_conditioned_raw','raw',True)]
    results={};rows=[]
    for name,mode,conditioned in specs:
        log('fit '+name);sm=Model(mode).fit(sf).calibrate(sc);em=Model(mode).fit(ef).calibrate(ec) if conditioned else sm
        im,ri=evaluate(sm,ir,'IndustrialTextileDataset',name);ex,rex=evaluate(em,er,'MVTec-AD carpet',name);both=gate(im) and gate(ex);results[name]={'feature_mode':mode,'conditioning':'per_pattern_family_normal_only' if conditioned else 'source_frozen','internal':im,'external':ex,'gate_internal':gate(im),'gate_external':gate(ex),'gate_both':both};rows+=ri+rex
    sfpass=any(results[n]['gate_both'] for n in ['M1_robust_appearance_source_frozen','M2_self_similarity_source_frozen']);pc=results['M3_pattern_conditioned_raw']['gate_both'];verdict='PASS_SOURCE_FROZEN' if sfpass else 'PASS_PATTERN_CONDITIONED_ONLY' if pc else 'PASS_WITH_RESTRICTIONS' if any(v['gate_internal'] or v['gate_external'] for v in results.values()) else 'FAIL_DOMAIN_NORMALIZATION'
    payload={'release':'v0.7.0a1','claim':CLAIM,'threshold_protocol':'normal_calibration_q0.95','source':itd,'external':mv,'split_counts':{'source_fit':len(sf),'source_calibration':len(sc),'external_fit':len(ef),'external_calibration':len(ec)},'verdict':verdict,'criteria':{'roc_auc_min':.8,'fnr_max':.2,'fpr_max':.2,'p95_latency_ms_max':250},'results':results};(O/'domain_normalization_experiment.json').write_text(json.dumps(payload,indent=2))
    with (O/'domain_normalization_predictions.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    lines=['# WeaveVision v0.7.0a1 Domain Normalization','',f'Verdict: **{verdict}**','', '| Method | Ext AUROC | Ext FNR | Ext FPR | Ext P95 ms | Gate |','|---|---:|---:|---:|---:|---|']
    for n,v in results.items():x=v['external'];lines.append(f"| {n} | {x['roc_auc']:.4f} | {x['fnr']:.4f} | {x['fpr']:.4f} | {x['p95_latency_ms']:.3f} | {v['gate_both']} |")
    lines+=['','Claim: `OPEN_SOURCE_TEXTILE_PROXY_ONLY`. Not company validation.'];(O/'NORMALIZATION_SUMMARY.md').write_text('\n'.join(lines))
    html='<html><meta charset=utf-8><style>body{font-family:Arial;max-width:1200px;margin:auto}table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:7px}</style><h1>WeaveVision Domain Normalization</h1><b>'+verdict+'</b><table><tr><th>Method</th><th>Internal AUROC</th><th>External AUROC</th><th>External FNR</th><th>External FPR</th><th>P95 ms</th><th>Gate</th></tr>'+''.join(f"<tr><td>{n}</td><td>{v['internal']['roc_auc']}</td><td>{v['external']['roc_auc']}</td><td>{v['external']['fnr']}</td><td>{v['external']['fpr']}</td><td>{v['external']['p95_latency_ms']}</td><td>{v['gate_both']}</td></tr>" for n,v in results.items())+'</table><p>Research-only public proxy; not a company-line validation.</p></html>';(O/'domain_normalization_report.html').write_text(html)
    print(json.dumps({'verdict':verdict,'results':results},indent=2))
if __name__=='__main__':main()
