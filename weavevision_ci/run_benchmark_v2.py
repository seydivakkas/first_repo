from __future__ import annotations

import json
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download

import benchmark


EXTERNAL_NAME = "MVTec-AD carpet via DefectSpectrum mirror"


def acquire_external_carpet():
    download_root = benchmark.DL / "mvtec_carpet"
    snapshot_root = Path(
        snapshot_download(
            repo_id="DefectSpectrum/Defect_Spectrum",
            repo_type="dataset",
            allow_patterns=["DS-MVTec/carpet/image/**"],
            local_dir=download_root,
        )
    )
    source_root = snapshot_root / "DS-MVTec" / "carpet" / "image"
    target_root = benchmark.D / "external_carpet"
    marker = target_root / ".done.json"
    if marker.exists():
        return json.loads(marker.read_text(encoding="utf-8"))

    shutil.rmtree(target_root, ignore_errors=True)
    good_target = target_root / "test" / "good"
    defect_target = target_root / "test" / "defect"
    good_target.mkdir(parents=True, exist_ok=True)
    defect_target.mkdir(parents=True, exist_ok=True)

    good_images = benchmark.imgs(source_root / "good")
    defect_images = []
    defect_counts = {}
    for directory in sorted(source_root.iterdir()):
        if not directory.is_dir() or directory.name.lower() == "good":
            continue
        images = benchmark.imgs(directory)
        defect_counts[directory.name] = len(images)
        defect_images.extend((directory.name, image) for image in images)

    if not good_images or not defect_images:
        inventory = [str(path.relative_to(source_root)) for path in benchmark.imgs(source_root)[:40]]
        raise RuntimeError(
            "MVTec carpet mirror did not expose both good and defect images. "
            f"Inventory: {inventory}"
        )

    for index, source in enumerate(good_images[:80]):
        shutil.copy2(source, good_target / f"good_{index:04d}{source.suffix.lower()}")
    for index, (defect_type, source) in enumerate(defect_images[:80]):
        safe_type = defect_type.replace(" ", "_")
        shutil.copy2(
            source,
            defect_target / f"{safe_type}_{index:04d}{source.suffix.lower()}",
        )

    metadata = {
        "dataset": EXTERNAL_NAME,
        "upstream": "MVTec AD carpet",
        "mirror": "DefectSpectrum/Defect_Spectrum",
        "license_policy": "RESEARCH_ONLY_CC_BY_NC_SA_4_0",
        "root": str(target_root),
        "good_available": len(good_images),
        "defect_available": len(defect_images),
        "defect_counts": defect_counts,
        "good_selected": min(80, len(good_images)),
        "defect_selected": min(80, len(defect_images)),
        "raw_fabrid_status": "BLOCKED_BY_MENDELEY_CLOUDFLARE_ON_GITHUB_RUNNER",
        "threshold_recalibrated": False,
        "model_refit": False,
    }
    marker.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    for path in [benchmark.W, benchmark.D, benchmark.DL, benchmark.O]:
        path.mkdir(parents=True, exist_ok=True)

    itd = benchmark.acquire_itd()
    internal_root = Path(itd["root"])
    train_images = benchmark.imgs(internal_root / "train" / "good")
    calibration = train_images[-28:]
    fit_images = train_images[: min(180, len(train_images) - 28)]
    benchmark.log(f"fit={len(fit_images)} cal={len(calibration)}")

    model = benchmark.Model()
    model.fit(fit_images)
    model.calibrate(calibration)
    model.save(benchmark.O / "public_proxy_texture_memory.npz")

    internal_metrics, internal_rows = benchmark.evaluate(
        model,
        internal_root,
        "IndustrialTextileDataset",
    )

    external = acquire_external_carpet()
    external_metrics, external_rows = benchmark.evaluate(
        model,
        Path(external["root"]),
        EXTERNAL_NAME,
        80,
    )

    benchmark.report(
        internal_metrics,
        external_metrics,
        internal_rows + external_rows,
        {"itd": itd, "external": external},
    )

    replacements = {
        "RAW-FABRID": "MVTec-AD carpet external fallback",
        "Not a company-line validation.": (
            "Research-only external benchmark; not a company-line validation."
        ),
    }
    for filename in ["BENCHMARK_SUMMARY.md", "public_proxy_report.html"]:
        path = benchmark.O / filename
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    report_path = benchmark.O / "benchmark_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["release"] = "v0.6.0b1"
    payload["external_dataset"] = EXTERNAL_NAME
    payload["external_license_policy"] = "RESEARCH_ONLY_CC_BY_NC_SA_4_0"
    payload["raw_fabrid_status"] = "BLOCKED_BY_MENDELEY_CLOUDFLARE_ON_GITHUB_RUNNER"
    payload["threshold_recalibrated_on_external"] = False
    payload["model_refit_on_external"] = False
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {"internal": internal_metrics, "external": external_metrics},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
