from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def download_with_resume(url: str, output: Path, retries: int = 6) -> tuple[bool, str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_suffix(output.suffix + ".part")

    for attempt in range(1, retries + 1):
        offset = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": "ADIM-01E-0O-A5-V2/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"

        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status = getattr(response, "status", 200)
                append = bool(offset and status == 206)
                if offset and not append:
                    offset = 0
                mode = "ab" if append else "wb"
                with part.open(mode) as handle:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        handle.write(block)
            if part.stat().st_size == 0:
                raise RuntimeError("Downloaded file is empty")
            part.replace(output)
            return True, f"downloaded {output.stat().st_size} bytes"
        except Exception as exc:
            detail = f"attempt {attempt}/{retries}: {type(exc).__name__}: {exc}"
            if attempt == retries:
                return False, detail
            time.sleep(min(3 * attempt, 15))
    return False, "unreachable"


def run(cmd: list[str], cwd: Path) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--skip-optional", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    incoming = root / "incoming"
    derived = root / "derived"
    logs = root / "logs"
    config_path = root / "config" / "assets.json"
    assets = json.loads(config_path.read_text(encoding="utf-8"))
    incoming.mkdir(exist_ok=True)
    derived.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)

    rows: list[dict[str, object]] = []
    required_failure = False
    for name, asset in assets.items():
        if args.skip_optional and not asset.get("required", False):
            rows.append({"asset": name, "status": "SKIPPED_OPTIONAL", "url": "", "detail": ""})
            continue
        output = incoming / asset["filename"]
        if output.is_file() and output.stat().st_size > 0:
            rows.append({"asset": name, "status": "PRESENT", "url": "", "detail": str(output.stat().st_size)})
            continue
        success = False
        last_detail = ""
        last_url = ""
        for url in asset["urls"]:
            last_url = url
            success, last_detail = download_with_resume(url, output)
            if success:
                break
        rows.append({
            "asset": name,
            "status": "DOWNLOADED" if success else "FAILED",
            "url": last_url,
            "detail": last_detail,
        })
        if asset.get("required", False) and not success:
            required_failure = True

    with (logs / "transfer_log_cross_platform.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["asset", "status", "url", "detail"])
        writer.writeheader()
        writer.writerows(rows)

    if required_failure or args.download_only:
        return 10 if required_failure else 0

    py = sys.executable
    commands = [
        [py, "scripts/validate_raw_assets.py", "--incoming", str(incoming), "--config", str(config_path), "--output", str(derived / "raw_asset_validation_v2.json")],
        [py, "scripts/filter_dft_a897_v2.py", "--incoming", str(incoming), "--output", str(derived)],
        [py, "scripts/extract_a897_osm.py", "--pbf", str(incoming / assets["scotland_pbf"]["filename"]), "--output", str(derived), "--passing-distance-m", "120"],
        [py, "scripts/make_gate_v2.py", "--root", str(root)],
    ]
    for command in commands:
        code = run(command, root)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
