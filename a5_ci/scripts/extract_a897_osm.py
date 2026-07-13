from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import osmium
from pyproj import Transformer
from shapely.geometry import LineString, Point, mapping
from shapely.ops import transform, unary_union


REF_PATTERN = re.compile(r"(^|[;,/\s])A897($|[;,/\s])", re.IGNORECASE)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tags_dict(tags) -> dict[str, str]:
    return {tag.k: tag.v for tag in tags}


class Handler(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self.route_ways: list[dict] = []
        self.route_relations: list[dict] = []
        self.passing_points: list[dict] = []

    def node(self, node) -> None:
        tags = tags_dict(node.tags)
        if tags.get("highway") != "passing_place":
            return
        if not node.location.valid():
            return

        self.passing_points.append(
            {
                "osm_type": "node",
                "osm_id": int(node.id),
                "version": int(node.version),
                "timestamp": str(node.timestamp),
                "lon": float(node.location.lon),
                "lat": float(node.location.lat),
                "tags": tags,
            }
        )

    def way(self, way) -> None:
        tags = tags_dict(way.tags)
        ref = tags.get("ref", "")
        is_route = bool(REF_PATTERN.search(ref))
        is_passing = tags.get("highway") == "passing_place"

        if not (is_route or is_passing):
            return

        coordinates = []
        for node_ref in way.nodes:
            try:
                location = node_ref.location
                if location.valid():
                    coordinates.append(
                        (float(location.lon), float(location.lat))
                    )
            except osmium.InvalidLocationError:
                continue

        if is_route and len(coordinates) >= 2:
            self.route_ways.append(
                {
                    "osm_type": "way",
                    "osm_id": int(way.id),
                    "version": int(way.version),
                    "timestamp": str(way.timestamp),
                    "tags": tags,
                    "coordinates": coordinates,
                }
            )

        if is_passing and coordinates:
            lon = sum(x for x, _ in coordinates) / len(coordinates)
            lat = sum(y for _, y in coordinates) / len(coordinates)
            self.passing_points.append(
                {
                    "osm_type": "way",
                    "osm_id": int(way.id),
                    "version": int(way.version),
                    "timestamp": str(way.timestamp),
                    "lon": lon,
                    "lat": lat,
                    "tags": tags,
                }
            )

    def relation(self, relation) -> None:
        tags = tags_dict(relation.tags)
        ref = tags.get("ref", "")
        if not REF_PATTERN.search(ref):
            return

        self.route_relations.append(
            {
                "osm_type": "relation",
                "osm_id": int(relation.id),
                "version": int(relation.version),
                "timestamp": str(relation.timestamp),
                "tags": tags,
                "members": [
                    {
                        "type": member.type,
                        "ref": int(member.ref),
                        "role": member.role,
                    }
                    for member in relation.members
                ],
            }
        )


def feature(geometry, properties):
    return {
        "type": "Feature",
        "geometry": mapping(geometry),
        "properties": properties,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--passing-distance-m",
        type=float,
        default=120.0,
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    handler = Handler()
    handler.apply_file(
        str(args.pbf),
        locations=True,
        idx="flex_mem",
    )

    if not handler.route_ways:
        raise RuntimeError("No OSM ways with ref=A897 were found.")

    route_features = []
    route_lines_wgs84 = []
    for record in handler.route_ways:
        line = LineString(record["coordinates"])
        route_lines_wgs84.append(line)
        properties = {
            key: value
            for key, value in record.items()
            if key != "coordinates"
        }
        properties["tags"] = json.dumps(
            properties["tags"],
            ensure_ascii=False,
            sort_keys=True,
        )
        route_features.append(feature(line, properties))

    centerline_path = args.output / "a897_centerline.geojson"
    centerline_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": route_features,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest_path = args.output / "a897_way_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "osm_id",
                "version",
                "timestamp",
                "name",
                "ref",
                "highway",
                "oneway",
                "maxspeed",
                "node_count",
            ],
        )
        writer.writeheader()
        for record in handler.route_ways:
            tags = record["tags"]
            writer.writerow(
                {
                    "osm_id": record["osm_id"],
                    "version": record["version"],
                    "timestamp": record["timestamp"],
                    "name": tags.get("name", ""),
                    "ref": tags.get("ref", ""),
                    "highway": tags.get("highway", ""),
                    "oneway": tags.get("oneway", ""),
                    "maxspeed": tags.get("maxspeed", ""),
                    "node_count": len(record["coordinates"]),
                }
            )

    relations_path = args.output / "a897_route_relations.json"
    relations_path.write_text(
        json.dumps(
            handler.route_relations,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    to_bng = Transformer.from_crs(
        "EPSG:4326",
        "EPSG:27700",
        always_xy=True,
    ).transform

    route_union_bng = unary_union(
        [transform(to_bng, line) for line in route_lines_wgs84]
    )

    selected = []
    for record in handler.passing_points:
        point_wgs84 = Point(record["lon"], record["lat"])
        point_bng = transform(to_bng, point_wgs84)
        distance = float(point_bng.distance(route_union_bng))

        if distance <= args.passing_distance_m:
            item = dict(record)
            item["distance_to_a897_m"] = distance
            selected.append(item)

    passing_features = []
    for item in selected:
        properties = dict(item)
        lon = properties.pop("lon")
        lat = properties.pop("lat")
        properties["tags"] = json.dumps(
            properties["tags"],
            ensure_ascii=False,
            sort_keys=True,
        )
        passing_features.append(
            feature(Point(lon, lat), properties)
        )

    passing_geojson = args.output / "a897_passing_places.geojson"
    passing_geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": passing_features,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    passing_csv = args.output / "a897_passing_places.csv"
    with passing_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "osm_type",
                "osm_id",
                "version",
                "timestamp",
                "lon",
                "lat",
                "distance_to_a897_m",
                "name",
                "source",
            ],
        )
        writer.writeheader()
        for item in selected:
            tags = item["tags"]
            writer.writerow(
                {
                    "osm_type": item["osm_type"],
                    "osm_id": item["osm_id"],
                    "version": item["version"],
                    "timestamp": item["timestamp"],
                    "lon": item["lon"],
                    "lat": item["lat"],
                    "distance_to_a897_m": item[
                        "distance_to_a897_m"
                    ],
                    "name": tags.get("name", ""),
                    "source": tags.get("source", ""),
                }
            )

    report = {
        "pbf": str(args.pbf),
        "pbf_sha256": sha256(args.pbf),
        "route_way_count": len(handler.route_ways),
        "route_relation_count": len(handler.route_relations),
        "all_passing_place_feature_count": len(
            handler.passing_points
        ),
        "a897_nearby_passing_place_count": len(selected),
        "passing_distance_threshold_m": args.passing_distance_m,
        "centerline_sha256": sha256(centerline_path),
        "way_manifest_sha256": sha256(manifest_path),
        "passing_places_geojson_sha256": sha256(
            passing_geojson
        ),
        "passing_places_csv_sha256": sha256(passing_csv),
        "inventory_scope": (
            "OSM features tagged highway=passing_place in the "
            "frozen Scotland snapshot and within the declared "
            "distance of A897 ways."
        ),
    }

    (args.output / "a897_osm_extraction_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
