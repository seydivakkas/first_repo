from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans

import run_phase_residual_v09 as v09

ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "weavevision_ci" / "outputs_v10"
CLAIM = "OPEN_SOURCE_TEXTILE_PROXY_ONLY"
GRID = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00]


def normal_p(score, calibration):
    values = np.asarray(calibration, np.float64)
    return float((1 + np.count_nonzero(values >= score)) / (len(values) + 1))


def signature(path):
    image = v09.base.rgb_image(path)
    a = v09.base.rgb_array(image)
    g = v09.base.gray(a)
    gx, gy, mag = v09.base.grad(g)
    angle = np.arctan2(gy, gx)
    weight = mag + 1e-6
    coherence = abs(np.sum(weight * np.exp(2j * angle)) / np.sum(weight))
    spectrum = abs(np.fft.rfft2(g - g.mean())) ** 2
    yy = np.fft.fftfreq(g.shape[0])[:, None]
    xx = np.fft.rfftfreq(g.shape[1])[None, :]
    radius = np.sqrt(xx * xx + yy * yy)
    high = spectrum[radius >= 0.25].sum() / max(float(spectrum.sum()), 1e-9)
    return np.asarray([
        g.mean(), np.percentile(g, 90) - np.percentile(g, 10),
        mag.mean(), coherence, high,
    ], np.float64)


def quantiles(values):
    a = np.asarray(values, np.float64)
    return {
        "min": float(a.min()), "q10": float(np.quantile(a, .1)),
        "median": float(np.median(a)), "q90": float(np.quantile(a, .9)),
        "max": float(a.max()),
    }


def overlap(a, b, bins=24):
    a, b = np.asarray(a), np.asarray(b)
    lo, hi = min(a.min(), b.min()), max(a.max(), b.max())
    if hi <= lo:
        return 1.0
    ha = np.histogram(a, bins=bins, range=(lo, hi))[0].astype(float)
    hb = np.histogram(b, bins=bins, range=(lo, hi))[0].astype(float)
    ha /= max(ha.sum(), 1); hb /= max(hb.sum(), 1)
    return float(np.minimum(ha, hb).sum())


def separation(good, defect):
    good, defect = np.asarray(good), np.asarray(defect)
    diff = defect[:, None] - good[None, :]
    return float((np.count_nonzero(diff > 0) + .5 * np.count_nonzero(diff == 0)) / diff.size)


def confusion(labels, predictions):
    tn = fp = fn = tp = 0
    for y, z in zip(labels, predictions):
        if y == 0 and z == 0: tn += 1
        elif y == 0: fp += 1
        elif z == 0: fn += 1
        else: tp += 1
    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp}


def selective(labels, pvalues, gamma):
    states, yl, zp = [], [], []
    for y, p in zip(labels, pvalues):
        state = "REVIEW" if p <= .10 else "CERTIFY_NORMAL_LIKE" if p >= gamma else "ABSTAIN_RESIDUAL_UNCERTAIN"
        states.append(state)
        if state != "ABSTAIN_RESIDUAL_UNCERTAIN":
            yl.append(y); zp.append(int(state == "REVIEW"))
    cm = confusion(yl, zp)
    decided = len(yl)
    positives = cm["tp"] + cm["fn"]
    negatives = cm["tn"] + cm["fp"]
    return {
        "certify_normal_like_p_min": gamma,
        "review_p_max": .10,
        "decided": decided,
        "abstained": len(labels) - decided,
        "coverage": decided / len(labels),
        "selective_risk": (cm["fp"] + cm["fn"]) / max(decided, 1),
        "fnr": cm["fn"] / max(positives, 1),
        "fpr": cm["fp"] / max(negatives, 1),
        "positive_coverage": positives / max(sum(y == 1 for y in labels), 1),
        "negative_coverage": negatives / max(sum(y == 0 for y in labels), 1),
        **cm,
    }


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def subgroup(rows, key, positive, overall):
    grouped = defaultdict(list)
    for row in rows: grouped[row[key]].append(row)
    error_key = "is_fn" if positive else "is_fp"
    total_errors = sum(row[error_key] for row in rows)
    output = []
    for name in sorted(grouped):
        items = grouped[name]
        errors = sum(row[error_key] for row in items)
        rate = errors / len(items)
        contribution = errors / max(total_errors, 1)
        result = {
            key: name, "count": len(items), "errors": errors,
            "error_rate": rate, "error_contribution": contribution,
            "concentrated": bool(len(items) >= 5 and (contribution >= .40 or rate >= overall + .15)),
            "hard_domain_abstain": sum(row["hard_domain_abstain"] for row in items),
            "guard_band_review": sum(row["domain_guard_band"] for row in items),
            **quantiles([row["r1_score"] for row in items]),
        }
        if positive: result.update({"tp": len(items)-errors, "fn": errors, "fnr": rate})
        else: result.update({"tn": len(items)-errors, "fp": errors, "fpr": rate})
        output.append(result)
    return output


def main():
    O.mkdir(parents=True, exist_ok=True)
    itd, itd_meta = v09.base.acquire_itd()
    mvtec, mvtec_meta = v09.base.acquire_mvtec()
    train = v09.base.imgs(mvtec / "train" / "good")
    fit, calibration = train[:40], train[40:49]
    good, defect = v09.base.groups(mvtec)
    mismatch = (v09.base.imgs(itd / "test" / "good") + sum([
        v09.base.imgs(path) for path in sorted((itd / "test").iterdir())
        if path.is_dir() and path.name != "good"
    ], []))[:114]
    v09.base.log(f"fit={len(fit)} cal={len(calibration)} good={len(good)} defect={len(defect)} mismatch={len(mismatch)}")

    model = v09.base.Model().fit(fit)
    dcal = [model.dscore(path) for path in calibration]
    dbase, dmargin, dhard = v09.guard_band(dcal)
    rcal = [v09.residual_score(model, path, "R1_PHASE_EQUIVALENT_LOCAL_CORRELATION") for path in calibration]
    rthreshold = v09.base.conformal(rcal, .10)

    fit_features = np.stack([signature(path) for path in fit])
    feature_center = np.median(fit_features, axis=0)
    feature_scale = np.maximum(1.4826 * np.median(abs(fit_features-feature_center), axis=0), 1e-6)
    fit_z = (fit_features-feature_center)/feature_scale
    clusterer = KMeans(n_clusters=3, random_state=42, n_init=20).fit(fit_z)
    good_clusters = clusterer.predict((np.stack([signature(path) for path in good])-feature_center)/feature_scale)
    cluster_by_path = {str(path): f"T{int(cluster)}" for path, cluster in zip(good, good_clusters)}

    mismatch_scores = [model.dscore(path) for path in mismatch]
    mismatch_recall = sum(score > dhard for score in mismatch_scores) / len(mismatch_scores)

    rows, latencies = [], []
    for label, paths in [(0, good), (1, defect)]:
        for path in paths:
            started = time.perf_counter()
            ds = model.dscore(path)
            rs = v09.residual_score(model, path, "R1_PHASE_EQUIVALENT_LOCAL_CORRELATION")
            latency = (time.perf_counter()-started)*1000
            latencies.append(latency)
            hard = ds > dhard
            guard = dbase < ds <= dhard
            predicted = int(rs > rthreshold + 1e-8)
            p = normal_p(rs, rcal)
            row = {
                "path": str(path), "label": label,
                "defect_type": path.parent.name if label else "good",
                "normal_texture_group": cluster_by_path.get(str(path), "NOT_APPLICABLE"),
                "domain_score": ds, "domain_base_threshold": dbase,
                "domain_hard_threshold": dhard, "domain_guard_band": int(guard),
                "hard_domain_abstain": int(hard), "r1_score": rs,
                "r1_threshold": rthreshold, "r1_predicted": predicted,
                "normal_conformal_p": p,
                "is_fn": int(label == 1 and predicted == 0 and not hard),
                "is_fp": int(label == 0 and predicted == 1 and not hard),
                "latency_ms": latency,
            }
            rows.append(row)

    authorized = [row for row in rows if not row["hard_domain_abstain"]]
    ag = [row for row in authorized if row["label"] == 0]
    ad = [row for row in authorized if row["label"] == 1]
    overall_fnr = sum(row["is_fn"] for row in ad) / len(ad)
    overall_fpr = sum(row["is_fp"] for row in ag) / len(ag)
    defect_groups = subgroup(ad, "defect_type", True, overall_fnr)
    normal_groups = subgroup(ag, "normal_texture_group", False, overall_fpr)
    for item in normal_groups:
        index = int(item["normal_texture_group"][1:])
        raw_centroid = feature_center + feature_scale * clusterer.cluster_centers_[index]
        item["centroid_luminance"] = float(raw_centroid[0])
        item["centroid_contrast"] = float(raw_centroid[1])
        item["centroid_gradient"] = float(raw_centroid[2])
        item["centroid_orientation_coherence"] = float(raw_centroid[3])
        item["centroid_high_frequency"] = float(raw_centroid[4])

    gs = [row["r1_score"] for row in ag]
    ds = [row["r1_score"] for row in ad]
    overlaps = [{
        "comparison": "all_defects_vs_good", "normal_count": len(gs), "defect_count": len(ds),
        "pairwise_separation": separation(gs, ds), "overlap_coefficient": overlap(gs, ds),
        "normal_median": float(np.median(gs)), "defect_median": float(np.median(ds)),
        "r1_threshold": rthreshold,
    }]
    for name in sorted(set(row["defect_type"] for row in ad)):
        values = [row["r1_score"] for row in ad if row["defect_type"] == name]
        overlaps.append({
            "comparison": name + "_vs_good", "normal_count": len(gs), "defect_count": len(values),
            "pairwise_separation": separation(gs, values), "overlap_coefficient": overlap(gs, values),
            "normal_median": float(np.median(gs)), "defect_median": float(np.median(values)),
            "r1_threshold": rthreshold,
        })

    labels = [row["label"] for row in authorized]
    pvalues = [row["normal_conformal_p"] for row in authorized]
    curve = []
    for gamma in GRID:
        item = selective(labels, pvalues, gamma)
        item["end_to_end_coverage"] = item["decided"] / len(rows)
        item["domain_abstained"] = len(rows)-len(authorized)
        item["passes"] = bool(
            item["coverage"] >= .50 and item["selective_risk"] <= .20 and
            item["fnr"] <= .20 and item["fpr"] <= .20 and
            item["tp"]+item["fn"] >= 10 and item["tn"]+item["fp"] >= 10
        )
        curve.append(item)
    passing = sorted([x for x in curve if x["passes"]], key=lambda x: (-x["coverage"], x["selective_risk"], -x["certify_normal_like_p_min"]))
    authorized_policy = passing[0] if passing else None
    verdict = "PASS_SELECTIVE_POLICY" if authorized_policy else "PASS_ERROR_ANATOMY_ONLY"

    ordered = sorted(latencies)
    report = {
        "release": "v0.10.0a1", "claim": CLAIM, "verdict": verdict,
        "r1_frozen": True, "test_label_threshold_tuning": False,
        "source": itd_meta, "family": mvtec_meta,
        "split_counts": {"fit":len(fit),"calibration":len(calibration),"test_good":len(good),"test_defect":len(defect),"mismatch":len(mismatch),"authorized_good":len(ag),"authorized_defect":len(ad)},
        "domain": {"base_threshold":dbase,"guard_margin":dmargin,"hard_threshold":dhard,"mismatch_recall":mismatch_recall,"compatible_good_hard_false_abstain":sum(row["hard_domain_abstain"] for row in rows if row["label"]==0)/len(good)},
        "r1": {"threshold":rthreshold,"calibration_scores":rcal,"overall_post_domain_fnr":overall_fnr,"overall_post_domain_fpr":overall_fpr,"p95_latency_ms":ordered[max(0,math.ceil(.95*len(ordered))-1)]},
        "error_concentration": {"fn_subgroups":[x["defect_type"] for x in defect_groups if x["concentrated"]],"fp_texture_groups":[x["normal_texture_group"] for x in normal_groups if x["concentrated"]]},
        "defect_subgroups": defect_groups, "normal_texture_subgroups": normal_groups,
        "texture_feature_order":["luminance_mean","robust_contrast","gradient_mean","orientation_coherence","high_frequency_ratio"],
        "score_overlap": overlaps,
        "selective_policy": {"review_p_max":.10,"certify_grid":GRID,"curve":curve,"authorized_policy":authorized_policy,"production_authority":"NONE" if not authorized_policy else "OPEN_SOURCE_NORMAL_LIKE_DECISION_SUPPORT_ONLY"},
        "production_deployment":"BLOCKED",
    }
    (O/"r1_error_selective_experiment.json").write_text(json.dumps(report, indent=2))
    write_csv(O/"r1_predictions_with_subgroups.csv", rows)
    write_csv(O/"r1_defect_subgroups.csv", defect_groups)
    write_csv(O/"r1_normal_texture_subgroups.csv", normal_groups)
    write_csv(O/"r1_score_overlap.csv", overlaps)
    write_csv(O/"r1_coverage_risk_curve.csv", curve)

    summary = ["# WeaveVision v0.10.0a1 R1 Error Decomposition", "", f"Verdict: **{verdict}**", "", f"Overall FNR: **{overall_fnr:.4f}**", f"Overall FPR: **{overall_fpr:.4f}**", f"FN concentration: **{report['error_concentration']['fn_subgroups']}**", f"FP texture concentration: **{report['error_concentration']['fp_texture_groups']}**", f"Authorized policy: **{authorized_policy}**", "", "R1 frozen; calibration-only p-values; no test tuning."]
    (O/"R1_ERROR_SELECTIVE_SUMMARY.md").write_text("\n".join(summary)+"\n")
    html_rows = "".join(f"<tr><td>{x['certify_normal_like_p_min']}</td><td>{x['coverage']:.4f}</td><td>{x['selective_risk']:.4f}</td><td>{x['fnr']:.4f}</td><td>{x['fpr']:.4f}</td><td>{x['passes']}</td></tr>" for x in curve)
    (O/"r1_error_selective_report.html").write_text(f"<html><meta charset=utf-8><style>body{{font-family:Arial;max-width:1200px;margin:auto}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:7px}}</style><h1>WeaveVision v0.10.0a1</h1><h2>{verdict}</h2><p>FN groups: {report['error_concentration']['fn_subgroups']}</p><p>FP texture groups: {report['error_concentration']['fp_texture_groups']}</p><table><tr><th>gamma</th><th>coverage</th><th>risk</th><th>FNR</th><th>FPR</th><th>pass</th></tr>{html_rows}</table><p>{CLAIM}; not company validation.</p></html>")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
