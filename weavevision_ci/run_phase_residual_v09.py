from __future__ import annotations

import csv
import json
import math
import statistics
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score

import run_domain_residual_v08 as base

ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "weavevision_ci" / "outputs_v09"
CLAIM = "OPEN_SOURCE_TEXTILE_PROXY_ONLY"


def guard_band(scores, alpha=0.10):
    values = np.sort(np.asarray(scores, np.float32))
    if len(values) < 3:
        raise RuntimeError("Need at least three domain calibration scores")
    threshold = base.conformal(values, alpha)
    tail = float(values[-1] - values[-2])
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)) * 1.4826)
    margin = max(tail, 0.5 * mad, 0.02 * max(threshold, 1e-6), 1e-6)
    return threshold, margin, threshold + margin


def shift_without_wrap(array, dy, dx):
    shifted = np.roll(array, (dy, dx), (0, 1))
    valid = np.ones(array.shape, bool)
    if dy > 0:
        valid[:dy] = False
    elif dy < 0:
        valid[dy:] = False
    if dx > 0:
        valid[:, :dx] = False
    elif dx < 0:
        valid[:, dx:] = False
    return shifted, valid


def r1_map(query, reference, local_shift=4, shift_step=2, radius=5):
    q = base.gray(base.robust(query))
    r = base.gray(base.robust(reference))
    qm = base.blur(q, radius)
    qv = np.maximum(base.blur(q * q, radius) - qm * qm, 1e-6)
    best = np.full(q.shape, np.inf, np.float32)
    offsets = range(-local_shift, local_shift + 1, shift_step)
    for dy in offsets:
        for dx in offsets:
            shifted, valid = shift_without_wrap(r, dy, dx)
            rm = base.blur(shifted, radius)
            rv = np.maximum(base.blur(shifted * shifted, radius) - rm * rm, 1e-6)
            covariance = base.blur(q * shifted, radius) - qm * rm
            ncc = covariance / np.sqrt(qv * rv)
            residual = (1.0 - np.clip(ncc, -1.0, 1.0)).astype(np.float32)
            residual[~valid] = np.inf
            best = np.minimum(best, residual)
    finite = np.isfinite(best)
    best[~finite] = float(np.median(best[finite])) if finite.any() else 2.0
    return base.blur(np.clip(best, 0.0, 2.0), 1).astype(np.float32)


def radial_mask(shape, low=0.06, high=0.48):
    yy = np.fft.fftfreq(shape[0])[:, None]
    xx = np.fft.fftfreq(shape[1])[None, :]
    radius = np.sqrt(xx * xx + yy * yy)
    return ((radius >= low) & (radius <= high)).astype(np.float32)


def r2_map(query, references):
    q = base.gray(base.robust(query))
    normal = np.stack([base.gray(base.robust(reference)) for reference in references])
    query_fft = np.fft.fft2(q)
    query_amplitude = np.abs(query_fft)
    query_phase = np.exp(1j * np.angle(query_fft))
    family_amplitude = np.median(np.abs(np.fft.fft2(normal, axes=(-2, -1))), axis=0)
    mask = radial_mask(q.shape)
    amplitude = query_amplitude * (1.0 - mask) + family_amplitude * mask
    reconstruction = np.fft.ifft2(amplitude * query_phase).real.astype(np.float32)
    return base.blur(np.abs(q - reconstruction), 2).astype(np.float32)


def nearest_refs(model, path):
    image = base.rgb_image(path)
    query = base.rgb_array(image)
    distances = base.nearest((base.image_desc(image) - model.ic) / model.isc, model.ids)
    count = min(3, len(distances))
    indices = np.argpartition(distances, count - 1)[:count]
    return query, model.refs[indices]


def residual_score(model, path, method):
    query, references = nearest_refs(model, path)
    if method == "R0_NEAREST_REFERENCE_PIXEL":
        heatmap = np.min(np.stack([base.residual(query, ref) for ref in references]), axis=0)
    elif method == "R1_PHASE_EQUIVALENT_LOCAL_CORRELATION":
        heatmap = np.min(np.stack([r1_map(query, ref) for ref in references]), axis=0)
    elif method == "R2_FREQUENCY_BAND_RECONSTRUCTION":
        heatmap = r2_map(query, references)
    else:
        raise ValueError(method)
    return float(np.quantile(heatmap, 0.99))


def metrics(labels, scores, predictions, latencies):
    y = np.asarray(labels)
    s = np.asarray(scores)
    z = np.asarray(predictions)
    tn, fp, fn, tp = confusion_matrix(y, z, labels=[0, 1]).ravel()
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    ordered = sorted(latencies)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
    return {
        "count": len(labels),
        "roc_auc": round(float(roc_auc_score(y, s)), 4) if len(set(labels)) == 2 else None,
        "average_precision": round(float(average_precision_score(y, s)), 4) if len(set(labels)) == 2 else None,
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "fnr": round(float(fn / max(fn + tp, 1)), 4),
        "fpr": round(float(fp / max(fp + tn, 1)), 4),
        "cm": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "mean_latency_ms": round(float(statistics.mean(ordered)), 3),
        "p95_latency_ms": round(float(p95), 3),
    }


def gate(value):
    return bool(
        value["roc_auc"] is not None
        and value["roc_auc"] >= 0.80
        and value["fnr"] <= 0.20
        and value["fpr"] <= 0.20
        and value["p95_latency_ms"] <= 250.0
    )


def main():
    O.mkdir(parents=True, exist_ok=True)
    itd, itd_meta = base.acquire_itd()
    mvtec, mvtec_meta = base.acquire_mvtec()
    train = base.imgs(mvtec / "train" / "good")
    fit, calibration = train[:40], train[40:49]
    good, defect = base.groups(mvtec)
    mismatch = (
        base.imgs(itd / "test" / "good")
        + sum(
            [
                base.imgs(path)
                for path in sorted((itd / "test").iterdir())
                if path.is_dir() and path.name != "good"
            ],
            [],
        )
    )[:114]
    base.log(
        f"fit={len(fit)} calibration={len(calibration)} good={len(good)} "
        f"defect={len(defect)} mismatch={len(mismatch)}"
    )

    model = base.Model().fit(fit)
    domain_calibration = [model.dscore(path) for path in calibration]
    domain_base, guard_margin, domain_hard = guard_band(domain_calibration)
    good_domain = [model.dscore(path) for path in good]
    defect_domain = [model.dscore(path) for path in defect]
    mismatch_domain = [model.dscore(path) for path in mismatch]

    domain_labels = [0] * (len(good_domain) + len(defect_domain)) + [1] * len(mismatch_domain)
    domain_scores = good_domain + defect_domain + mismatch_domain
    domain_predictions = [int(score > domain_hard) for score in domain_scores]
    dtn, dfp, dfn, dtp = confusion_matrix(domain_labels, domain_predictions, labels=[0, 1]).ravel()
    mismatch_recall = dtp / max(dtp + dfn, 1)
    false_abstain = sum(score > domain_hard for score in good_domain) / len(good_domain)
    domain_gate = mismatch_recall >= 0.95 and false_abstain <= 0.10

    methods = [
        "R0_NEAREST_REFERENCE_PIXEL",
        "R1_PHASE_EQUIVALENT_LOCAL_CORRELATION",
        "R2_FREQUENCY_BAND_RECONSTRUCTION",
    ]
    thresholds = {
        method: base.conformal([residual_score(model, path, method) for path in calibration], 0.10)
        for method in methods
    }

    results = {}
    rows = []
    entries = [(0, path) for path in good] + [(1, path) for path in defect]
    for method in methods:
        all_labels, all_scores, all_predictions, all_latencies = [], [], [], []
        auth_labels, auth_scores, auth_predictions, auth_latencies = [], [], [], []
        threshold = thresholds[method]
        for label, path in entries:
            started = time.perf_counter()
            dscore = model.dscore(path)
            rscore = residual_score(model, path, method)
            latency = (time.perf_counter() - started) * 1000.0
            predicted = int(rscore > threshold + 1e-8)
            hard_abstain = dscore > domain_hard
            guard_review = domain_base < dscore <= domain_hard
            state = (
                "ABSTAIN_DOMAIN_MISMATCH"
                if hard_abstain
                else "REVIEW"
                if predicted or guard_review
                else "NORMAL"
            )
            rows.append(
                {
                    "method": method,
                    "path": str(path),
                    "label": label,
                    "domain_score": dscore,
                    "domain_base_threshold": domain_base,
                    "domain_hard_threshold": domain_hard,
                    "guard_band": int(guard_review),
                    "hard_abstain": int(hard_abstain),
                    "residual_score": rscore,
                    "residual_threshold": threshold,
                    "residual_predicted": predicted,
                    "state": state,
                    "latency_ms": latency,
                }
            )
            all_labels.append(label)
            all_scores.append(rscore)
            all_predictions.append(predicted)
            all_latencies.append(latency)
            if not hard_abstain:
                auth_labels.append(label)
                auth_scores.append(rscore)
                auth_predictions.append(predicted)
                auth_latencies.append(latency)
        full = metrics(all_labels, all_scores, all_predictions, all_latencies)
        authorized = metrics(auth_labels, auth_scores, auth_predictions, auth_latencies)
        results[method] = {
            "threshold": round(float(threshold), 6),
            "full_sealed_family_test": full,
            "post_hard_abstain": authorized,
            "coverage": round(len(auth_labels) / len(all_labels), 4),
            "residual_gate": gate(authorized),
        }

    passing = [name for name, value in results.items() if value["residual_gate"]]
    if domain_gate and passing:
        verdict = "PASS_PHASE_EQUIVARIANT_RESIDUAL"
    elif domain_gate:
        verdict = "PASS_DOMAIN_GUARD_ONLY"
    elif passing:
        verdict = "PASS_RESIDUAL_WITH_DOMAIN_RESTRICTION"
    else:
        verdict = "PASS_WITH_RESTRICTIONS"

    report = {
        "release": "v0.9.0a1",
        "claim": CLAIM,
        "verdict": verdict,
        "source": itd_meta,
        "family": mvtec_meta,
        "split_counts": {
            "fit": len(fit),
            "calibration": len(calibration),
            "test_good": len(good),
            "test_defect": len(defect),
            "mismatch": len(mismatch),
        },
        "threshold_policy": {
            "residual": "split_conformal_alpha_0.10_per_method",
            "domain": "split_conformal_plus_calibration_only_guard_band",
            "test_tuning": False,
        },
        "domain": {
            "base_threshold": round(float(domain_base), 6),
            "guard_margin": round(float(guard_margin), 6),
            "hard_mismatch_threshold": round(float(domain_hard), 6),
            "roc_auc": round(float(roc_auc_score(domain_labels, domain_scores)), 4),
            "mismatch_recall": round(float(mismatch_recall), 4),
            "compatible_good_hard_false_abstain": round(float(false_abstain), 4),
            "compatible_good_guard_band_rate": round(
                sum(domain_base < score <= domain_hard for score in good_domain) / len(good_domain), 4
            ),
            "compatible_defect_hard_abstain": round(
                sum(score > domain_hard for score in defect_domain) / len(defect_domain), 4
            ),
            "cm": {"tn": int(dtn), "fp": int(dfp), "fn": int(dfn), "tp": int(dtp)},
            "gate": domain_gate,
        },
        "residuals": results,
        "passing_residuals": passing,
        "criteria": {
            "mismatch_recall_min": 0.95,
            "compatible_good_false_abstain_max": 0.10,
            "residual_roc_auc_min": 0.80,
            "residual_fnr_max": 0.20,
            "residual_fpr_max": 0.20,
            "p95_latency_ms_max": 250.0,
        },
        "production_deployment": "BLOCKED",
    }
    (O / "phase_residual_experiment.json").write_text(json.dumps(report, indent=2))
    with (O / "phase_residual_predictions.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# WeaveVision v0.9.0a1 Phase Residual",
        "",
        f"Verdict: **{verdict}**",
        "",
        f"Domain mismatch recall: **{mismatch_recall:.4f}**",
        f"Compatible-good hard false abstain: **{false_abstain:.4f}**",
        "",
        "| Residual | AUROC | FNR | FPR | P95 ms | Coverage | Gate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, value in results.items():
        item = value["post_hard_abstain"]
        lines.append(
            f"| {name} | {item['roc_auc']:.4f} | {item['fnr']:.4f} | "
            f"{item['fpr']:.4f} | {item['p95_latency_ms']:.3f} | "
            f"{value['coverage']:.4f} | {value['residual_gate']} |"
        )
    lines.extend(["", "No test image was used for threshold selection.", f"Claim: `{CLAIM}`."])
    (O / "PHASE_RESIDUAL_SUMMARY.md").write_text("\n".join(lines) + "\n")

    html_rows = []
    for name, value in results.items():
        item = value["post_hard_abstain"]
        html_rows.append(
            f"<tr><td>{name}</td><td>{item['roc_auc']:.4f}</td><td>{item['fnr']:.4f}</td>"
            f"<td>{item['fpr']:.4f}</td><td>{item['p95_latency_ms']:.3f}</td>"
            f"<td>{value['coverage']:.4f}</td><td>{value['residual_gate']}</td></tr>"
        )
    html = (
        "<html><meta charset=utf-8><style>body{font-family:Arial;max-width:1200px;margin:auto}"
        "table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:7px}</style>"
        f"<h1>WeaveVision v0.9.0a1</h1><h2>{verdict}</h2>"
        f"<p>Mismatch recall: <b>{mismatch_recall:.4f}</b>; false abstain: <b>{false_abstain:.4f}</b>.</p>"
        "<table><tr><th>Residual</th><th>AUROC</th><th>FNR</th><th>FPR</th>"
        "<th>P95 ms</th><th>Coverage</th><th>Gate</th></tr>"
        + "".join(html_rows)
        + f"</table><p>{CLAIM}; not company validation.</p></html>"
    )
    (O / "phase_residual_report.html").write_text(html)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
