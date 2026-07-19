from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tarfile
import zipfile
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_pdf(path: Path) -> tuple[bool, str]:
    if path.stat().st_size < 1024:
        return False, "PDF is implausibly small."
    with path.open("rb") as f:
        if f.read(5) != b"%PDF-":
            return False, "Missing PDF signature."
    return True, "PDF signature and minimum size valid."


def validate_tar(path: Path) -> tuple[bool, str]:
    try:
        with tarfile.open(path, mode="r:*") as archive:
            members = [m for m in archive.getmembers() if m.isfile()]
            if not members:
                return False, "Archive contains no regular files."
    except (tarfile.TarError, OSError) as exc:
        return False, f"Unreadable archive: {exc}"
    return True, f"Readable source archive with {len(members)} files."


def validate_zip(path: Path, require_csv: bool) -> tuple[bool, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                return False, f"ZIP CRC failure: {bad}"
            files = [x.filename for x in archive.infolist() if not x.is_dir()]
            if not files:
                return False, "ZIP is empty."
            if require_csv and not any(x.lower().endswith(".csv") for x in files):
                return False, "ZIP contains no CSV member."
    except (zipfile.BadZipFile, OSError) as exc:
        return False, f"Unreadable ZIP: {exc}"
    return True, f"ZIP valid with {len(files)} files."


def validate_hgt_gzip(
    path: Path,
    accepted_sizes: set[int],
) -> tuple[bool, str, int | None]:
    total = 0
    try:
        with gzip.open(path, "rb") as source:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        return False, f"Invalid gzip/CRC: {exc}", None

    if total not in accepted_sizes:
        return (
            False,
            f"Unexpected HGT uncompressed size: {total}",
            total,
        )
    return True, f"Valid HGT gzip, uncompressed bytes={total}.", total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    report: dict[str, object] = {
        "assets": {},
        "publisher_md5_match": False,
        "all_required_assets_valid": False,
    }

    all_required_valid = True

    for key, asset in config.items():
        path = args.incoming / asset["filename"]
        record: dict[str, object] = {
            "path": str(path),
            "required": bool(asset.get("required", False)),
            "exists": path.is_file(),
            "valid": False,
        }

        if not path.is_file() or path.stat().st_size == 0:
            record["detail"] = "Missing or zero-byte file."
            if record["required"]:
                all_required_valid = False
            report["assets"][key] = record
            continue

        record["size_bytes"] = path.stat().st_size
        record["sha256"] = digest(path, "sha256")
        validation = asset.get("validation")
        valid = True
        detail = "Nonzero file."

        if validation == "pdf":
            valid, detail = validate_pdf(path)
        elif validation == "tar":
            valid, detail = validate_tar(path)
        elif validation == "zip_csv":
            valid, detail = validate_zip(path, require_csv=True)
        elif validation == "zip":
            valid, detail = validate_zip(path, require_csv=False)
        elif validation == "hgt_gzip":
            valid, detail, uncompressed = validate_hgt_gzip(
                path,
                set(asset["accepted_uncompressed_sizes"]),
            )
            record["uncompressed_size_bytes"] = uncompressed
        elif validation == "md5_text":
            text = path.read_text(encoding="utf-8", errors="replace")
            valid = bool(re.search(r"\b[0-9a-fA-F]{32}\b", text))
            detail = "MD5 digest found." if valid else "No MD5 digest found."

        record["valid"] = valid
        record["detail"] = detail

        if record["required"] and not valid:
            all_required_valid = False

        report["assets"][key] = record

    pbf_cfg = config["scotland_pbf"]
    pbf = args.incoming / pbf_cfg["filename"]
    md5_file = args.incoming / config["scotland_md5"]["filename"]

    size_match = (
        pbf.is_file()
        and pbf.stat().st_size == int(pbf_cfg["expected_size_bytes"])
    )
    report["pbf_expected_size_bytes"] = pbf_cfg["expected_size_bytes"]
    report["pbf_size_match"] = size_match

    if not size_match:
        all_required_valid = False

    if pbf.is_file() and md5_file.is_file():
        match = re.search(
            r"\b([0-9a-fA-F]{32})\b",
            md5_file.read_text(encoding="utf-8", errors="replace"),
        )
        if match:
            expected = match.group(1).lower()
            actual = digest(pbf, "md5")
            report["publisher_md5_expected"] = expected
            report["publisher_md5_actual"] = actual
            report["publisher_md5_match"] = expected == actual

    if not report["publisher_md5_match"]:
        all_required_valid = False

    report["all_required_assets_valid"] = all_required_valid
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all_required_valid else 4


if __name__ == "__main__":
    raise SystemExit(main())
