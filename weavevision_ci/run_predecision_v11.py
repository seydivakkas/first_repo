from __future__ import annotations

import csv, json, math, statistics, time
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix, roc_auc_score

import run_domain_residual_v08 as base
import run_phase_residual_v09 as phase

ROOT = Path(__file__).resolve().parents[1]
O = ROOT / 'weavevision_ci' / 'outputs_v11'
CLAIM = 'OPEN_SOURCE_TEXTILE_PROXY_ONLY'
R1 = 'R1_PHASE_EQUIVALENT_LOCAL_CORRELATION'


def signature(path):
    a = base.rgb_array(base.rgb_image(path)); g = base.gray(a); gx, gy, mag = base.grad(g)
    ang = np.arctan2(gy, gx); w = mag + 1e-6
    coherence = abs(np.sum(w * np.exp(2j * ang)) / np.sum(w))
    z = g - g.mean(); s = abs(np.fft.rfft2(z)) ** 2
    yy = np.fft.fftfreq(g.shape[0])[:, None]; xx = np.fft.rfftfreq(g.shape[1])[None, :]
    total = max(float(s.sum()), 1e-9)
    return np.array([g.mean(), np.percentile(g,90)-np.percentile(g,10), mag.mean(), coherence,
                     s[np.sqrt(xx*xx+yy*yy)>=.25].sum()/total], np.float64)


def kmeans(x, k=3):
    x=np.asarray(x,np.float64); c=np.median(x,0); sc=np.maximum(1.4826*np.median(abs(x-c),0),1e-6); z=(x-c)/sc
    chosen=[int(np.argmin(np.sum(z*z,1)))]
    while len(chosen)<k:
        d=np.min(np.stack([np.sum((z-z[i])**2,1) for i in chosen]),0); d[chosen]=-1; chosen.append(int(np.argmax(d)))
    cent=z[chosen].copy(); labels=np.zeros(len(z),int)
    for _ in range(100):
        nl=np.argmin(np.stack([np.sum((z-v)**2,1) for v in cent],1),1)
        if np.array_equal(nl,labels): labels=nl; break
        labels=nl
        for j in range(k):
            if np.any(labels==j): cent[j]=z[labels==j].mean(0)
    raw=cent*sc+c; t0=min(range(k),key=lambda j:(raw[j,3],raw[j,4]))
    margins=[]
    for q in z:
        d=np.sum((cent-q)**2,1); margins.append(np.min(np.delete(d,t0))-d[t0])
    return cent,c,sc,t0,max(float(np.quantile(abs(np.array(margins)),.10)),1e-6),raw


def t0_score(f, mem):
    cent,c,sc,t0,margin,_=mem; q=(f-c)/sc; d=np.sum((cent-q)**2,1)
    return float(np.min(np.delete(d,t0))-d[t0])


def t0_state(score, margin):
    return 'T0_RISK' if score>=margin else 'T0_UNCERTAIN' if score>-margin else 'ORDINARY'


def sat(a):
    hi=a.max(2); lo=a.min(2); return (hi-lo)/np.maximum(hi,1e-6)


def align(ref,q):
    dy,dx=base.phase(base.gray(ref),base.gray(q)); r=np.roll(ref,(dy,dx),(0,1)).copy()
    if dy>0:r[:dy]=q[:dy]
    elif dy<0:r[dy:]=q[dy:]
    if dx>0:r[:,:dx]=q[:,:dx]
    elif dx<0:r[:,dx:]=q[:,dx:]
    return r


def weak_features(q,ref):
    r=align(ref,q); qn=base.robust(q); rn=base.robust(r); app=np.mean(abs(qn-rn),2)
    qg,rg=base.gray(qn),base.gray(rn); qx,qy,qm=base.grad(qg); rx,ry,rm=base.grad(rg)
    cos=(qx*rx+qy*ry)/np.maximum(qm*rm,1e-6); structural=abs(qm-rm)+.25*(1-np.clip(cos,-1,1))
    ach=abs(base.gray(q)-base.gray(r))*(1-np.maximum(sat(q),sat(r)))
    q75=float(np.quantile(app,.75)); q99=float(np.quantile(app,.99))
    return np.array([q99,q99/max(q75+.02,1e-6),np.quantile(ach,.99),np.quantile(structural,.95)],np.float64)


def nearest_ref(model,path,exclude=None):
    im=base.rgb_image(path); desc=(base.image_desc(im)-model.ic)/model.isc; d=base.nearest(desc,model.ids)
    if exclude is not None:d[exclude]=np.inf
    return base.rgb_array(im),model.refs[int(np.argmin(d))]


def conformal(scores,alpha=.1):
    v=np.sort(np.asarray(scores,float)); k=math.ceil((len(v)+1)*(1-alpha)); return float(v[min(max(k-1,0),len(v)-1)])


def fit_weak(model,fit,cal):
    ff=np.stack([weak_features(*nearest_ref(model,p,i)) for i,p in enumerate(fit)])
    c=np.median(ff,0); sc=np.maximum(1.4826*np.median(abs(ff-c),0),1e-4); w=np.array([1,.5,.75,-.75])
    def score(p):
        f=weak_features(*nearest_ref(model,p)); return float(((f-c)/sc)@w),f
    cs=np.array([score(p)[0] for p in cal]); bt=conformal(cs); sv=np.sort(cs)
    tail=float(sv[-1]-sv[-2]); mad=float(1.4826*np.median(abs(sv-np.median(sv)))); margin=max(tail,.5*mad,.02*max(abs(bt),1),1e-6)
    return score,bt,bt+margin,c,sc


def binary_metrics(target,scores,routed):
    y=np.array(target,int); s=np.array(scores,float); z=np.array(routed,int); tn,fp,fn,tp=confusion_matrix(y,z,labels=[0,1]).ravel()
    return {'count':len(y),'positive_count':int(y.sum()),'negative_count':int(len(y)-y.sum()),
            'roc_auc':round(float(roc_auc_score(y,s)),4) if len(set(y))==2 else None,
            'recall':round(float(tp/max(tp+fn,1)),4),'false_route_rate':round(float(fp/max(fp+tn,1)),4),
            'cm':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}}


def main():
    for p in [base.W,base.D,base.DL,O]:p.mkdir(parents=True,exist_ok=True)
    itd,itdm=base.acquire_itd(); mv,mvm=base.acquire_mvtec(); train=base.imgs(mv/'train'/'good'); fit,cal=train[:40],train[40:49]
    good,bad=base.groups(mv); mismatch=(base.imgs(itd/'test'/'good')+sum([base.imgs(p) for p in sorted((itd/'test').iterdir()) if p.is_dir() and p.name!='good'],[]))[:114]
    base.log(f'fit={len(fit)} cal={len(cal)} good={len(good)} defect={len(bad)} mismatch={len(mismatch)}')
    model=base.Model().fit(fit); r1t=conformal([phase.residual_score(model,p,R1) for p in cal]); dg=phase.guard_band([model.dscore(p) for p in cal])
    tmem=kmeans(np.stack([signature(p) for p in fit])); weak,wb,wh,wc,ws=fit_weak(model,fit,cal)
    mismatch_recall=sum(model.dscore(p)>dg[2] for p in mismatch)/len(mismatch)
    rows=[]; lats=[]
    for label,paths in [(0,good),(1,bad)]:
      for p in paths:
        st=time.perf_counter(); ds=model.dscore(p); ts=t0_score(signature(p),tmem); tst=t0_state(ts,tmem[4]); wscore,wfeat=weak(p)
        wst='WLD_RISK' if wscore>wh else 'WLD_UNCERTAIN' if wscore>wb else 'ORDINARY'; rs=phase.residual_score(model,p,R1); lat=(time.perf_counter()-st)*1000; lats.append(lat)
        hard=ds>dg[2]; dguard=dg[0]<ds<=dg[2]; rp=rs>r1t+1e-8
        route='ABSTAIN_DOMAIN_MISMATCH' if hard else 'ABSTAIN_ERROR_MODE_UNKNOWN' if tst=='T0_UNCERTAIN' or wst=='WLD_UNCERTAIN' else 'HUMAN_REVIEW' if dguard or tst=='T0_RISK' or wst=='WLD_RISK' or rp else 'NORMAL_LIKE_SUPPORT'
        rows.append({'path':str(p),'label':label,'defect_type':p.parent.name if label else 'good','domain_score':ds,'hard_domain':int(hard),'domain_guard':int(dguard),
          't0_score':ts,'t0_state':tst,'weak_score':wscore,'weak_state':wst,'weak_A99':wfeat[0],'weak_Asp':wfeat[1],'weak_Ach99':wfeat[2],'weak_G95':wfeat[3],
          'r1_score':rs,'r1_threshold':r1t,'r1_positive':int(rp),'r1_fp':int(label==0 and rp and not hard),'r1_fn':int(label==1 and not rp and not hard),'route':route,'latency_ms':lat})
    cg=[r for r in rows if r['label']==0 and not r['hard_domain']]; cd=[r for r in rows if r['label']==1 and not r['hard_domain']]
    tm=binary_metrics([r['r1_fp'] for r in cg],[r['t0_score'] for r in cg],[int(r['t0_state']=='T0_RISK') for r in cg])
    wm=binary_metrics([r['r1_fn'] for r in cd],[r['weak_score'] for r in cd],[int(r['weak_state']=='WLD_RISK') for r in cd])
    metal=[r for r in cd if r['defect_type']=='metal_contamination' and r['r1_fn']]; mr=sum(r['weak_state']=='WLD_RISK' for r in metal)/len(metal) if metal else 0
    tg=tm['roc_auc'] is not None and tm['roc_auc']>=.8 and tm['recall']>=.8 and tm['false_route_rate']<=.2 and tm['count']>=10
    wg=wm['roc_auc'] is not None and wm['roc_auc']>=.8 and wm['recall']>=.8 and wm['false_route_rate']<=.3 and mr>=.8
    states=Counter(r['route'] for r in rows); nd=sum(r['label']==1 for r in rows); nn=sum(r['label']==0 for r in rows)
    dns=sum(r['label']==1 and r['route']=='NORMAL_LIKE_SUPPORT' for r in rows); ns=sum(r['label']==0 and r['route']=='NORMAL_LIKE_SUPPORT' for r in rows)
    support=dns+ns; ordered=sorted(lats); p95=ordered[max(0,math.ceil(.95*len(ordered))-1)]
    routing={'route_counts':dict(states),'defect_review_or_abstain_recall':round(1-dns/nd,4),'defect_normal_support_rate':round(dns/nd,4),
      'normal_support_coverage':round(ns/nn,4),'normal_review_or_abstain_burden':round(1-ns/nn,4),'normal_like_support_contamination':round(dns/max(support,1),4),
      'mean_latency_ms':round(statistics.mean(lats),3),'p95_latency_ms':round(p95,3)}
    rg=routing['defect_review_or_abstain_recall']>=.9 and routing['defect_normal_support_rate']<=.1 and routing['normal_support_coverage']>=.2 and routing['p95_latency_ms']<=250
    verdict='PASS_IDENTIFIABLE_AND_ROUTABLE' if tg and wg and rg else 'PASS_T0_IDENTIFIABILITY_ONLY' if tg and not wg else 'PASS_WEAK_LOCAL_IDENTIFIABILITY_ONLY' if wg and not tg else 'PASS_PARTIAL_IDENTIFIABILITY' if max(tm['roc_auc'] or 0,wm['roc_auc'] or 0)>=.65 else 'FAIL_PREDECISION_IDENTIFIABILITY'
    report={'release':'v0.11.0a1','claim':CLAIM,'verdict':verdict,'integrity':{'r1_frozen':True,'r1_threshold_changed':False,'supervised_error_classifier':False,'test_label_threshold_tuning':False},
      'source':itdm,'family':mvm,'split_counts':{'fit':len(fit),'calibration':len(cal),'test_good':len(good),'test_defect':len(bad),'mismatch':len(mismatch)},
      'thresholds':{'r1':r1t,'domain_base':dg[0],'domain_hard':dg[2],'t0_margin':tmem[4],'weak_base':wb,'weak_hard':wh},'domain':{'mismatch_recall':round(mismatch_recall,4),'gate':mismatch_recall>=.95},
      't0_high_fp_identifiability':{**tm,'gate':tg},'weak_local_identifiability':{**wm,'metal_false_negative_count':len(metal),'metal_false_negative_recall':round(mr,4),'gate':wg},
      'routing':{**routing,'gate':rg},'authorization':{'risk_aware_routing':verdict=='PASS_IDENTIFIABLE_AND_ROUTABLE','automatic_acceptance_or_rejection':False,'production_deployment':False},
      't0_centroid_index':tmem[3],'t0_raw_centroid':tmem[5][tmem[3]].tolist(),'weak_feature_center':wc.tolist(),'weak_feature_scale':ws.tolist()}
    O.mkdir(parents=True,exist_ok=True); (O/'predecision_error_mode_experiment.json').write_text(json.dumps(report,indent=2))
    with (O/'predecision_predictions.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    for name,data in [('t0_identifiability.csv',{**tm,'gate':tg}),('weak_local_identifiability.csv',{**wm,'metal_false_negative_recall':mr,'gate':wg})]:
      with (O/name).open('w',newline='') as f:w=csv.writer(f);w.writerow(['metric','value']);[w.writerow([k,json.dumps(v) if isinstance(v,dict) else v]) for k,v in data.items()]
    with (O/'routing_states.csv').open('w',newline='') as f:w=csv.writer(f);w.writerow(['route','count']);[w.writerow(x) for x in sorted(states.items())]
    table=lambda x:''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k,v in x.items())
    (O/'predecision_error_mode_report.html').write_text(f'<html><meta charset=utf-8><style>body{{font-family:Arial;max-width:1100px;margin:auto}}table{{border-collapse:collapse}}th,td{{border:1px solid #ccc;padding:7px}}</style><h1>WeaveVision v0.11.0a1</h1><b>{verdict}</b><h2>T0</h2><table>{table({**tm,"gate":tg})}</table><h2>Weak local</h2><table>{table({**wm,"metal_fn_recall":mr,"gate":wg})}</table><h2>Routing</h2><table>{table({**routing,"gate":rg})}</table></html>')
    (O/'PREDECISION_SUMMARY.md').write_text(f'# WeaveVision v0.11.0a1\n\nVerdict: **{verdict}**\n\n```json\n{json.dumps(report,indent=2)}\n```\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
