from __future__ import annotations

import argparse, gzip, hashlib, json, math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, Point, shape
from shapely.ops import linemerge, transform, unary_union


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass
class Tile:
    data: np.ndarray
    south: float = 58.0
    west: float = -4.0
    north: float = 59.0
    east: float = -3.0

    def sample(self, lon, lat):
        n = self.data.shape[0]
        row = np.clip((self.north - lat) * (n - 1), 0, n - 1)
        col = np.clip((lon - self.west) * (n - 1), 0, n - 1)
        r0 = np.floor(row).astype(int); c0 = np.floor(col).astype(int)
        r1 = np.minimum(r0 + 1, n - 1); c1 = np.minimum(c0 + 1, n - 1)
        fr = row - r0; fc = col - c0
        return (
            self.data[r0, c0] * (1 - fr) * (1 - fc)
            + self.data[r0, c1] * (1 - fr) * fc
            + self.data[r1, c0] * fr * (1 - fc)
            + self.data[r1, c1] * fr * fc
        )


def load_tile(path: Path):
    with gzip.open(path, "rb") as f: raw = f.read()
    n = int(round(math.sqrt(len(raw) // 2)))
    if n * n * 2 != len(raw): raise ValueError("invalid HGT dimensions")
    data = np.frombuffer(raw, dtype=">i2").astype(float).reshape(n, n)
    data[data <= -32768] = np.nan
    data = np.nan_to_num(data, nan=float(np.nanmedian(data)))
    return Tile(data)


def ordered_route(path: Path):
    obj = json.loads(path.read_text(encoding="utf-8"))
    merged = linemerge(unary_union([shape(f["geometry"]) for f in obj["features"]]))
    if merged.geom_type != "LineString": raise ValueError(f"route type {merged.geom_type}")
    coords = list(merged.coords)
    if coords[0][1] > coords[-1][1]: coords.reverse()
    return LineString(coords)


def terrain_los(incoming: Path, derived: Path, output: Path):
    tile = load_tile(incoming / "N58W004.hgt.gz")
    route_wgs = ordered_route(derived / "a897_centerline.geojson")
    to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    route = transform(to_bng.transform, route_wgs)
    pp = pd.read_csv(derived / "a897_passing_places.csv")
    pp["chainage_m"] = [route.project(transform(to_bng.transform, Point(r.lon, r.lat))) for r in pp.itertuples(index=False)]
    pp = pp.sort_values("chainage_m").reset_index(drop=True)

    eye = target = 1.05
    step = 10.0
    radius = 7 / 6 * 6_371_000.0
    guard = 10.0
    rows = []
    for i in range(len(pp) - 1):
        a, b = pp.iloc[i], pp.iloc[i + 1]
        p0 = transform(to_bng.transform, Point(float(a.lon), float(a.lat)))
        p1 = transform(to_bng.transform, Point(float(b.lon), float(b.lat)))
        distance = p0.distance(p1)
        count = max(3, math.ceil(distance / step) + 1)
        t = np.linspace(0, 1, count)
        xs = p0.x + t * (p1.x - p0.x); ys = p0.y + t * (p1.y - p0.y)
        lons, lats = to_wgs.transform(xs, ys)
        z = tile.sample(np.asarray(lons), np.asarray(lats))
        ray = z[0] + eye + t * ((z[-1] + target) - (z[0] + eye))
        d1 = t * distance; d2 = distance - d1
        clearance = ray - (z + d1 * d2 / (2 * radius))
        inner = clearance[1:-1]
        minimum = float(inner.min())
        j = int(inner.argmin()) + 1
        cls = "ROBUST_TERRAIN_BLOCKED" if minimum < -guard else "MARGINAL_TERRAIN_BLOCKED" if minimum < 0 else "TERRAIN_CLEAR_OCCLUSIONS_UNMODELED"
        rows.append({
            "pair_index": i,
            "from_osm_id": int(a.osm_id), "to_osm_id": int(b.osm_id),
            "from_chainage_m": float(a.chainage_m), "to_chainage_m": float(b.chainage_m),
            "route_gap_m": float(b.chainage_m - a.chainage_m),
            "straight_distance_m": float(distance), "sample_count": count,
            "min_clearance_m": minimum, "minimum_lon": float(lons[j]), "minimum_lat": float(lats[j]),
            "classification": cls,
        })
    df = pd.DataFrame(rows)
    df.to_csv(output / "a897_adjacent_passing_place_terrain_los.csv", index=False)

    chain = np.arange(0, route.length + 1, 50.0)
    points = [route.interpolate(float(x)) for x in chain]
    lon, lat = to_wgs.transform(np.array([p.x for p in points]), np.array([p.y for p in points]))
    elev = tile.sample(np.asarray(lon), np.asarray(lat))
    pd.DataFrame({"chainage_m": chain, "lon": lon, "lat": lat, "srtm_surface_elevation_m": elev}).to_csv(output / "a897_srtm_surface_profile_50m.csv", index=False)

    counts = df["classification"].value_counts().to_dict()
    result = {
        "route_length_m": float(route.length), "passing_place_count": int(len(pp)), "adjacent_pair_count": int(len(df)),
        "eye_height_m": eye, "target_height_m": target, "sample_step_m": step,
        "effective_earth_radius_factor": 7 / 6, "vertical_uncertainty_guard_m": guard,
        "classification_counts": {str(k): int(v) for k, v in counts.items()},
        "los_product_present": True,
        "evidence_class": "TERRAIN_SURFACE_ONLY_NOT_FULL_INTERVISIBILITY",
        "limitations": [
            "SRTM is an approximately 30 m surface model, not a surveyed road profile.",
            "Cuttings, road crown, walls, buildings and vegetation dynamics are not separately modeled.",
            "Terrain-clear does not mean physically inter-visible.",
            "No interval-level single-track applicability or physical-inventory completeness claim is made.",
        ],
    }
    write_json(output / "terrain_los_summary.json", result)
    return result


def traffic_claim(derived: Path, output: Path):
    aadf = pd.read_csv(derived / "a897_dft_aadf.csv")
    raw = pd.read_csv(derived / "a897_dft_raw_counts.csv")
    counted = aadf[aadf["estimation_method"].astype(str).str.upper() == "COUNTED"]
    result = {
        "claim_id": "A897_TRAFFIC_HISTORICAL_ONLY_V1",
        "allowed_claims": [
            "DfT provides historical A897 count-point records for 2000-2025.",
            "Direct count evidence exists only on the extracted measured dates.",
            "Measured days may anchor retrospective descriptions and sensitivity scenarios.",
        ],
        "forbidden_claims": [
            "The data identify current 2026 directional arrival rates.",
            "Estimated AADF is equivalent to direct count evidence.",
            "Historical demand is stationary or deployment-representative.",
            "A controller calibrated to these records is currently validated.",
        ],
        "counted_aadf_rows": int(len(counted)), "estimated_aadf_rows": int(len(aadf) - len(counted)),
        "counted_years": sorted(int(x) for x in counted["year"].unique()),
        "raw_count_dates": sorted(str(x) for x in raw["count_date"].unique()),
        "latest_direct_count_year": int(pd.to_datetime(raw["count_date"]).dt.year.max()),
        "latest_dataset_year": int(aadf["year"].max()),
        "current_demand_claim_withdrawn": True, "historical_only_claim_frozen": True,
    }
    write_json(output / "historical_traffic_claim_contract.json", result)
    return result


def gate(root: Path, los, traffic):
    output = root / "b1_derived"
    source = json.loads((output / "source_repair_summary.json").read_text(encoding="utf-8"))
    result = {
        "friesen_dual_author_record_resolved": source["friesen"].get("resolution_status") == "RESOLVED_AS_DUAL_RECORD",
        "canonical_highland_2013_guideline_acquired": bool(source["highland"].get("canonical_guideline_acquired")),
        "direct_passing_bay_optimization_source_acquired": bool(source["baseline"].get("direct_passing_bay_optimization_source_acquired")),
        "physical_passing_place_inventory_verified": False,
        "terrain_los_product_generated": bool(los.get("los_product_present")),
        "full_visibility_evidence_established": False,
        "historical_only_traffic_claim_frozen": bool(traffic.get("historical_only_claim_frozen")),
        "current_2026_demand_calibration_established": False,
        "baseline_implementation_authorization": False,
        "replication_authorization": False,
        "manuscript_rewrite_authorization": False,
    }
    result["b1_repair_complete"] = all([
        result["friesen_dual_author_record_resolved"], result["canonical_highland_2013_guideline_acquired"],
        result["direct_passing_bay_optimization_source_acquired"], result["physical_passing_place_inventory_verified"],
        result["full_visibility_evidence_established"], result["historical_only_traffic_claim_frozen"],
    ])
    result["repeat_0o_b_authorization"] = result["b1_repair_complete"]
    result["next_allowed_operation"] = "REPEAT_ADIM_01E_0O_B" if result["repeat_0o_b_authorization"] else "CONTINUE_ADIM_01E_0O_B1_EVIDENCE_REPAIR_ONLY"
    write_json(output / "B1_GATE_RESULT.json", result)
    return result


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True); args = ap.parse_args()
    root = args.root.resolve(); output = root / "b1_derived"; output.mkdir(parents=True, exist_ok=True)
    los = terrain_los(root / "incoming", root / "derived", output)
    traffic = traffic_claim(root / "derived", output)
    result = gate(root, los, traffic)
    manifest = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest.append({"path": str(path.relative_to(root)), "size_bytes": path.stat().st_size, "sha256": h})
    write_json(output / "B1_FILE_MANIFEST.json", manifest)
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
