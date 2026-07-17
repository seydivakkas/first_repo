from __future__ import annotations
import csv, hashlib, html, json, math, os, re, shutil, statistics, time, zipfile
from pathlib import Path
import numpy as np, requests
from huggingface_hub import hf_hub_download
from PIL import Image, ImageDraw
from remotezip import RemoteZip
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_fscore_support, roc_auc_score

ROOT=Path(__file__).resolve().parents[1]; W=ROOT/'weavevision_ci'/'work'; O=ROOT/'weavevision_ci'/'outputs'; D=W/'datasets'; DL=W/'downloads'
EXT={'.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp'}; CLAIM='OPEN_SOURCE_TEXTILE_PROXY_ONLY'
def log(x): print(f'[{time.strftime("%H:%M:%S")}] {x}',flush=True)
def imgs(p): return sorted(x for x in p.rglob('*') if x.is_file() and x.suffix.lower() in EXT)
def rgb(p):
    with Image.open(p) as im:return im.convert('RGB').copy()
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()
def safe_rel(name,root):
    n=name.replace('\\','/'); r=n[len(root.rstrip('/'))+1:]
    if '..' in Path(r).parts: raise RuntimeError('unsafe zip member')
    return r

def acquire_itd():
    z=Path(hf_hub_download(repo_id='SimTho/IndustrialTextileDataset',repo_type='dataset',filename='ITD.zip',local_dir=DL/'itd'))
    out=D/'itd'; marker=out/'.done.json'
    if marker.exists():return json.loads(marker.read_text())
    shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
    with zipfile.ZipFile(z) as q:
        names=q.namelist(); roots={}
        for n in names:
            m=re.search(r'^(.*?)(type\d+cam\d+)/train/good/',n.replace('\\','/'))
            if m:roots[m.group(2)]=(m.group(1)+m.group(2)).strip('/')
        cat=os.getenv('ITD_CATEGORY','type1cam1');cat=cat if cat in roots else sorted(roots)[0];root=roots[cat]
        for n in names:
            nn=n.replace('\\','/')
            if nn.startswith(root+'/') and not n.endswith('/'):
                t=out/cat/safe_rel(n,root);t.parent.mkdir(parents=True,exist_ok=True)
                with q.open(n) as a,t.open('wb') as b:shutil.copyfileobj(a,b)
    p={'dataset':'IndustrialTextileDataset','license':'MIT','category':cat,'root':str(out/cat),'archive_bytes':z.stat().st_size,'archive_sha256':sha(z)}
    marker.write_text(json.dumps(p,indent=2));return p

def mendeley_url():
    s=requests.Session();s.headers['User-Agent']='WeaveVision/0.6.0b1'
    for e in ['https://api.data.mendeley.com/datasets/db6g85xsyg/files','https://api.data.mendeley.com/datasets/publics/db6g85xsyg/files']:
        try:
            r=s.get(e,params={'version':1,'$limit':100},timeout=60);r.raise_for_status();a=r.json();a=a if isinstance(a,list) else a.get('items',[])
            for x in a:
                if str(x.get('filename','')).lower().endswith('.zip'):
                    u=(x.get('content_details') or {}).get('download_url') or x.get('download_url')
                    if u:return u,x
        except Exception:pass
    return 'https://api.data.mendeley.com/datasets/db6g85xsyg/zip/file_downloaded?version=1',{'fallback':True}
def roots(names):
    r={}
    for o in names:
        n=o.replace('\\','/');l=n.lower()
        if Path(n).suffix.lower() not in EXT:continue
        for mark,key in [('/train/good/','train'),('/test/good/','good')]:
            if mark in l:
                root=n[:l.index(mark)];r.setdefault(root,{'train':[],'good':[],'bad':[]})[key].append(o);break
        else:
            m=re.search(r'/test/([^/]+)/',l)
            if m and m.group(1) not in {'good','normal','ground_truth','mask','masks'}:
                root=n[:m.start()];r.setdefault(root,{'train':[],'good':[],'bad':[]})['bad'].append(o)
    return {k:v for k,v in r.items() if all(v.values())}
def raw_subset():
    out=D/'raw'/'subset';marker=out.parent/'.done.json'
    if marker.exists():return json.loads(marker.read_text())
    shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
    url,meta=mendeley_url(); err=None
    try:
        with RemoteZip(url,initial_buffer_size=262144,support_suffix_range=True) as q:
            rr=roots(q.namelist());root,g=max(rr.items(),key=lambda x:sum(map(len,x[1].values())))
            lim={'train':180,'good':80,'bad':80}
            for k,ns in g.items():
                for n in sorted(ns)[:lim[k]]:
                    t=out/safe_rel(n,root);t.parent.mkdir(parents=True,exist_ok=True)
                    with q.open(n) as a,t.open('wb') as b:shutil.copyfileobj(a,b)
            p={'dataset':'RAW-FABRID','license':'CC BY 4.0','root':str(out),'archive_root':root,'mode':'range','counts':{k:min(len(v),lim[k]) for k,v in g.items()},'meta':meta}
            marker.write_text(json.dumps(p,indent=2));return p
    except Exception as e:err=f'{type(e).__name__}: {e}';log('range failed: '+err)
    z=DL/'raw'/'RAW_FABRID.zip';z.parent.mkdir(parents=True,exist_ok=True)
    with requests.get(url,stream=True,timeout=(60,900),allow_redirects=True,headers={'User-Agent':'WeaveVision/0.6.0b1'}) as r:
        r.raise_for_status()
        with z.open('wb') as f:
            for b in r.iter_content(8<<20):
                if b:f.write(b)
    with zipfile.ZipFile(z) as q:
        rr=roots(q.namelist());root,g=max(rr.items(),key=lambda x:sum(map(len,x[1].values())));lim={'train':180,'good':80,'bad':80}
        for k,ns in g.items():
            for n in sorted(ns)[:lim[k]]:
                t=out/safe_rel(n,root);t.parent.mkdir(parents=True,exist_ok=True)
                with q.open(n) as a,t.open('wb') as b:shutil.copyfileobj(a,b)
    p={'dataset':'RAW-FABRID','license':'CC BY 4.0','root':str(out),'archive_root':root,'mode':'full','archive_bytes':z.stat().st_size,'archive_sha256':sha(z),'range_error':err}
    marker.write_text(json.dumps(p,indent=2));return p

def feat(im,size=128,tile=16,stride=8):
    a=np.asarray(im.resize((size,size),Image.Resampling.BILINEAR),np.float32)/255.;g=a.mean(2);gx=np.zeros_like(g);gy=np.zeros_like(g);gx[:,1:-1]=(g[:,2:]-g[:,:-2])/2;gy[1:-1]=(g[2:]-g[:-2])/2;d=np.sqrt(gx*gx+gy*gy);f=[]
    for y in range(0,size-tile+1,stride):
        for x in range(0,size-tile+1,stride):
            p=a[y:y+tile,x:x+tile];q=g[y:y+tile,x:x+tile];e=d[y:y+tile,x:x+tile];h=np.histogram(q,8,(0,1))[0].astype(np.float32);h/=max(h.sum(),1)
            f.append(np.r_[p.mean((0,1)),p.std((0,1)),q.mean(),q.std(),np.percentile(q,10),np.percentile(q,90),e.mean(),e.std(),h])
    return np.asarray(f,np.float32),15
class Model:
    def fit(self,paths):
        x=np.concatenate([feat(rgb(p))[0] for p in paths]);self.c=np.median(x,0);mad=np.median(abs(x-self.c),0);self.s=np.maximum(1.4826*mad,.02);x=(x-self.c)/self.s
        rng=np.random.default_rng(42);self.mem=x[rng.choice(len(x),min(4096,len(x)),False)]
    def score(self,p):
        x,w=feat(rgb(p));x=(x-self.c)/self.s;out=[];ms=np.sum(self.mem*self.mem,1)[None,:]
        for i in range(0,len(x),256):
            q=x[i:i+256];out.extend(np.sqrt(np.maximum(np.sum(q*q,1)[:,None]+ms-2*q@self.mem.T,0)).min(1))
        a=np.asarray(out);return float(np.percentile(a,95)),a.reshape(w,w)
    def calibrate(self,paths):
        ss=[];pp=[]
        for p in paths:s,h=self.score(p);ss.append(s);pp.extend(h.ravel())
        self.th=float(np.quantile(ss,.995));self.pth=float(np.quantile(pp,.995));self.scale=max(np.median(abs(np.asarray(ss)-np.median(ss)))*1.4826,self.th*.08,.03)
    def predict(self,p):
        t=time.perf_counter();s,h=self.score(p);prob=float(1/(1+np.exp(-np.clip((s-self.th)/self.scale,-30,30))));return s,prob,int(s>=self.th),1000*(time.perf_counter()-t),h
    def save(self,p):np.savez_compressed(p,c=self.c,s=self.s,mem=self.mem,th=self.th,pth=self.pth,scale=self.scale)
def groups(root):
    good=imgs(root/'test'/'good');bad=[]
    for d in (root/'test').iterdir():
        if d.is_dir() and d.name.lower() not in {'good','normal','ground_truth','mask','masks'}:bad+=imgs(d)
    return good,sorted(bad)
def evaluate(m,root,name,limit=0):
    good,bad=groups(root);good=good[:limit] if limit else good;bad=bad[:limit] if limit else bad;rows=[]
    for y,ps in [(0,good),(1,bad)]:
        for p in ps:
            s,pr,z,lat,h=m.predict(p);rows.append({'dataset':name,'path':str(p),'label':y,'score':s,'probability':pr,'predicted':z,'latency_ms':lat,'heatmap':h})
    y=np.array([r['label'] for r in rows]);s=np.array([r['score'] for r in rows]);z=np.array([r['predicted'] for r in rows]);prec,rec,f1,_=precision_recall_fscore_support(y,z,average='binary',zero_division=0);tn,fp,fn,tp=confusion_matrix(y,z,labels=[0,1]).ravel();lat=sorted(r['latency_ms'] for r in rows)
    met={'good':len(good),'defect':len(bad),'roc_auc':round(float(roc_auc_score(y,s)),4),'average_precision':round(float(average_precision_score(y,s)),4),'precision':round(float(prec),4),'recall':round(float(rec),4),'f1':round(float(f1),4),'fnr':round(float(fn/max(fn+tp,1)),4),'fpr':round(float(fp/max(fp+tn,1)),4),'cm':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)},'mean_latency_ms':round(statistics.mean(lat),3),'p95_latency_ms':round(lat[max(0,math.ceil(.95*len(lat))-1)],3),'threshold':round(m.th,6)}
    return met,rows
def report(i,e,rows,receipts):
    O.mkdir(parents=True,exist_ok=True);payload={'release':'v0.6.0b1','claim':CLAIM,'model':'TextureMemoryModel frozen after ITD calibration','internal':i,'external':e,'acquisition':receipts,'forbidden_claim':'Not a Merinos or company-line validation.'};(O/'benchmark_report.json').write_text(json.dumps(payload,indent=2))
    with (O/'predictions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['dataset','path','label','score','probability','predicted','latency_ms']);[w.writerow([r[k] for k in ['dataset','path','label','score','probability','predicted','latency_ms']]) for r in rows]
    cards=[]
    for j,r in enumerate(([x for x in rows if x['label']!=x['predicted']]+rows)[:20]):
        im=rgb(Path(r['path']));im.thumbnail((640,440));d=ImageDraw.Draw(im);d.rectangle((0,0,min(im.width,500),24),fill='black');d.text((5,5),f"{r['dataset']} GT={r['label']} pred={r['predicted']} score={r['score']:.3f}",fill='white');p=O/'samples'/f'{j:02d}.jpg';p.parent.mkdir(parents=True,exist_ok=True);im.save(p);cards.append(f"<article><img src='samples/{p.name}'><p>{html.escape(p.name)}</p></article>")
    def table(x):return ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k,v in x.items() if k!='cm')
    page=f"<html><meta charset=utf-8><style>body{{font-family:Arial;max-width:1200px;margin:auto}}.g{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}img{{width:100%;height:220px;object-fit:contain}}table{{border-collapse:collapse}}td,th{{padding:6px;border:1px solid #ddd}}</style><h1>WeaveVision v0.6.0b1</h1><b>{CLAIM}</b><p>Frozen ITD model, RAW-FABRID external test. Not company validation.</p><h2>Internal</h2><table>{table(i)}</table><h2>External</h2><table>{table(e)}</table><div class=g>{''.join(cards)}</div></html>";(O/'public_proxy_report.html').write_text(page)
    (O/'BENCHMARK_SUMMARY.md').write_text(f"# WeaveVision v0.6.0b1\n\nClaim: `{CLAIM}`\n\n## Internal ITD\n\n```json\n{json.dumps(i,indent=2)}\n```\n\n## External RAW-FABRID\n\n```json\n{json.dumps(e,indent=2)}\n```\n\nNot a company-line validation.\n")
def main():
    for p in [W,D,DL,O]:p.mkdir(parents=True,exist_ok=True)
    a=acquire_itd();root=Path(a['root']);tr=imgs(root/'train'/'good');cal=tr[-28:];fit=tr[:min(180,len(tr)-28)];log(f'fit={len(fit)} cal={len(cal)}');m=Model();m.fit(fit);m.calibrate(cal);m.save(O/'public_proxy_texture_memory.npz');i,ri=evaluate(m,root,'IndustrialTextileDataset');b=raw_subset();e,rex=evaluate(m,Path(b['root']),'RAW-FABRID',80);report(i,e,ri+rex,{'itd':a,'raw':b});print(json.dumps({'internal':i,'external':e},indent=2))
if __name__=='__main__':main()
