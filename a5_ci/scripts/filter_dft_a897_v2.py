from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from pathlib import Path


DATASETS = {
    "count_points": "count_points.zip",
    "raw_counts": "dft_traffic_counts_raw_counts.zip",
    "aadf": "dft_traffic_counts_aadf.zip",
    "aadf_by_direction": "dft_traffic_counts_aadf_by_direction.zip",
}


def norm(value: str | None) -> str:
    return (value or "").strip().upper().replace(" ", "")


def column(fieldnames: list[str], *candidates: str) -> str | None:
    lookup = {norm(name): name for name in fieldnames}
    for candidate in candidates:
        if norm(candidate) in lookup:
            return lookup[norm(candidate)]
    return None


def filter_archive(
    archive_path: Path,
    output_path: Path,
    count_ids: set[str],
) -> dict[str, object]:
    row_count = 0
    counted_rows = 0
    estimated_rows = 0
    discovered_ids: set[str] = set()
    source_members: list[str] = []
    writer = None
    output_handle = None

    try:
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                if member.is_dir() or not member.filename.lower().endswith(".csv"):
                    continue

                source_members.append(member.filename)
                with archive.open(member) as raw:
                    text = io.TextIOWrapper(
                        raw,
                        encoding="utf-8-sig",
                        errors="replace",
                        newline="",
                    )
                    reader = csv.DictReader(text)
                    if not reader.fieldnames:
                        continue

                    road_col = column(
                        reader.fieldnames,
                        "road_name",
                        "roadname",
                        "road",
                    )
                    id_col = column(
                        reader.fieldnames,
                        "count_point_id",
                        "countpointid",
                        "count_point",
                    )
                    method_col = column(
                        reader.fieldnames,
                        "estimation_method",
                        "estimationmethod",
                    )

                    if writer is None:
                        output_handle = output_path.open(
                            "w",
                            newline="",
                            encoding="utf-8",
                        )
                        writer = csv.DictWriter(
                            output_handle,
                            fieldnames=reader.fieldnames,
                        )
                        writer.writeheader()

                    for row in reader:
                        road_match = bool(
                            road_col and norm(row.get(road_col)) == "A897"
                        )
                        cp_id = str(row.get(id_col, "")).strip() if id_col else ""
                        id_match = bool(cp_id and cp_id in count_ids)

                        if not (road_match or id_match):
                            continue

                        writer.writerow(row)
                        row_count += 1

                        if cp_id:
                            discovered_ids.add(cp_id)

                        method = norm(row.get(method_col)) if method_col else ""
                        if method == "COUNTED":
                            counted_rows += 1
                        elif method == "ESTIMATED":
                            estimated_rows += 1
    finally:
        if output_handle is not None:
            output_handle.close()

    if writer is None:
        output_path.write_text("", encoding="utf-8")

    return {
        "row_count": row_count,
        "counted_rows": counted_rows,
        "estimated_rows": estimated_rows,
        "count_point_ids": sorted(discovered_ids),
        "source_members": source_members,
        "output": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "road_name": "A897",
        "datasets": {},
    }

    count_ids: set[str] = set()

    for dataset in ("count_points", "aadf", "aadf_by_direction", "raw_counts"):
        archive = args.incoming / DATASETS[dataset]
        output = args.output / f"a897_dft_{dataset}.csv"

        if not archive.is_file():
            summary["datasets"][dataset] = {
                "status": "OPTIONAL_MISSING" if dataset == "aadf_by_direction"
                else "REQUIRED_MISSING",
                "row_count": 0,
                "counted_rows": 0,
            }
            continue

        result = filter_archive(archive, output, count_ids)
        count_ids.update(result["count_point_ids"])
        result["status"] = "FILTERED"
        summary["datasets"][dataset] = result

    cp_rows = summary["datasets"].get("count_points", {}).get("row_count", 0)
    aadf_rows = summary["datasets"].get("aadf", {}).get("row_count", 0)
    aadf_counted = summary["datasets"].get("aadf", {}).get("counted_rows", 0)
    raw_rows = summary["datasets"].get("raw_counts", {}).get("row_count", 0)

    summary["count_point_id_count"] = len(count_ids)
    summary["nonzero_count_point_evidence"] = cp_rows > 0 and len(count_ids) > 0
    summary["nonzero_aadf_evidence"] = aadf_rows > 0
    summary["measured_or_counted_evidence"] = raw_rows > 0 or aadf_counted > 0
    summary["official_dft_a897_evidence_pass"] = bool(
        summary["nonzero_count_point_evidence"]
        and summary["nonzero_aadf_evidence"]
        and summary["measured_or_counted_evidence"]
    )

    path = args.output / "a897_dft_filter_summary_v2.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["official_dft_a897_evidence_pass"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
