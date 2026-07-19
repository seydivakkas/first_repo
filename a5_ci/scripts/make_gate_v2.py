from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()

    root = args.root
    incoming = root / "incoming"
    derived = root / "derived"

    raw_report = json.loads(
        (derived / "raw_asset_validation_v2.json").read_text(encoding="utf-8")
    )
    dft_report = json.loads(
        (derived / "a897_dft_filter_summary_v2.json").read_text(encoding="utf-8")
    )
    osm_report = json.loads(
        (derived / "a897_osm_extraction_report.json").read_text(encoding="utf-8")
    )

    required_osm_files = (
        "a897_centerline.geojson",
        "a897_way_manifest.csv",
        "a897_route_relations.json",
        "a897_passing_places.geojson",
        "a897_passing_places.csv",
        "a897_osm_extraction_report.json",
    )
    osm_files_ok = all(
        (derived / name).is_file()
        and (derived / name).stat().st_size > 0
        for name in required_osm_files
    )

    gate = {
        "required_raw_assets_present_and_valid": bool(
            raw_report["all_required_assets_valid"]
        ),
        "direct_passing_place_rule_raw_pdf": bool(
            raw_report["assets"]["highland_rule_pdf"]["valid"]
        ),
        "primary_research_pdf_raw_custody": bool(
            raw_report["assets"]["friesen_pdf"]["valid"]
        ),
        "primary_source_archive_valid": bool(
            raw_report["assets"]["friesen_source"]["valid"]
        ),
        "geofabrik_exact_size_match": bool(raw_report["pbf_size_match"]),
        "geofabrik_publisher_md5_match": bool(
            raw_report["publisher_md5_match"]
        ),
        "a897_exact_osm_snapshot_extraction": bool(
            osm_files_ok and osm_report.get("route_way_count", 0) > 0
        ),
        "a897_osm_passing_place_inventory_generated": bool(
            osm_files_ok
            and "a897_nearby_passing_place_count" in osm_report
        ),
        "official_dft_a897_extraction": bool(
            dft_report["official_dft_a897_evidence_pass"]
        ),
        "official_dft_measured_or_counted_evidence": bool(
            dft_report["measured_or_counted_evidence"]
        ),
        "reproducible_dem_input_custody": bool(
            raw_report["assets"]["srtm_dem"]["valid"]
        ),
    }
    gate["a5_pass"] = all(gate.values())
    gate["adim_01e_0o_b_authorization"] = gate["a5_pass"]
    gate["baseline_implementation_authorization"] = False

    custody = {
        "raw_validation_report_sha256": sha256(
            derived / "raw_asset_validation_v2.json"
        ),
        "dft_filter_report_sha256": sha256(
            derived / "a897_dft_filter_summary_v2.json"
        ),
        "osm_extraction_report_sha256": sha256(
            derived / "a897_osm_extraction_report.json"
        ),
        "raw_assets": {},
        "derived_assets": {},
    }

    for path in sorted(incoming.glob("*")):
        if path.is_file() and path.stat().st_size > 0:
            custody["raw_assets"][path.name] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }

    for path in sorted(derived.glob("*")):
        if path.is_file() and path.stat().st_size > 0:
            custody["derived_assets"][path.name] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }

    (derived / "A5_CUSTODY_MANIFEST_V2.json").write_text(
        json.dumps(custody, indent=2),
        encoding="utf-8",
    )
    (derived / "A5_GATE_RESULT_V2.json").write_text(
        json.dumps(gate, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(gate, indent=2))
    return 0 if gate["a5_pass"] else 6


if __name__ == "__main__":
    raise SystemExit(main())
