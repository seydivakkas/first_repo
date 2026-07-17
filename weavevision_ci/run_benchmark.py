from __future__ import annotations

import html as html_module
import json
import re
from pathlib import Path

import requests

import benchmark as benchmark


DATASET_ID = "db6g85xsyg"
VERSION = 1


def _find_zip_file(value):
    if isinstance(value, dict):
        filename = str(value.get("filename") or value.get("name") or "")
        if filename.lower().endswith(".zip") or filename == "RAW_FABRID.zip":
            return value
        for child in value.values():
            result = _find_zip_file(child)
            if result:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _find_zip_file(child)
            if result:
                return result
    return None


def _download_target(file_object: dict, diagnostics: list[dict], source: str):
    details = file_object.get("content_details") or {}
    url = details.get("download_url") or file_object.get("download_url")
    file_id = file_object.get("id") or details.get("id") or file_object.get("file_id")
    if url:
        return url, {"source": source, "file": file_object, "diagnostics": diagnostics}
    if file_id:
        url = (
            f"https://api.data.mendeley.com/datasets/{DATASET_ID}/files/"
            f"{file_id}/file_downloaded?version={VERSION}"
        )
        return url, {
            "source": source,
            "file": file_object,
            "file_id": file_id,
            "diagnostics": diagnostics,
        }
    return None


def resolve_mendeley_url():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 WeaveVision/0.6.0b1",
            "Accept": (
                "application/json, "
                "application/vnd.mendeley-public-dataset.1+json, "
                "application/vnd.mendeley-public-dataset-files.1+json, */*"
            ),
        }
    )
    diagnostics: list[dict] = []
    endpoints = [
        f"https://api.data.mendeley.com/datasets/{DATASET_ID}",
        f"https://api.data.mendeley.com/datasets/{DATASET_ID}/files",
        f"https://api.data.mendeley.com/datasets/publics/{DATASET_ID}/files",
    ]
    accept_variants = [
        None,
        "application/vnd.mendeley-public-dataset.1+json",
        "application/vnd.mendeley-public-dataset-files.1+json",
        "application/json",
    ]
    for endpoint in endpoints:
        for accept in accept_variants:
            headers = {"Accept": accept} if accept else {}
            try:
                response = session.get(
                    endpoint,
                    params={"version": VERSION, "$limit": 100},
                    headers=headers,
                    timeout=60,
                )
                diagnostics.append(
                    {
                        "url": response.url,
                        "accept": accept,
                        "status": response.status_code,
                        "content_type": response.headers.get("content-type"),
                        "body_prefix": response.text[:160],
                    }
                )
                if response.ok:
                    file_object = _find_zip_file(response.json())
                    if file_object:
                        target = _download_target(file_object, diagnostics, "api")
                        if target:
                            benchmark.log("RAW-FABRID metadata resolved through Mendeley API")
                            return target
            except Exception as error:
                diagnostics.append(
                    {
                        "url": endpoint,
                        "accept": accept,
                        "error": f"{type(error).__name__}: {error}",
                    }
                )

    page_url = f"https://data.mendeley.com/datasets/{DATASET_ID}/{VERSION}"
    try:
        response = session.get(page_url, timeout=60)
        diagnostics.append(
            {
                "url": page_url,
                "status": response.status_code,
                "bytes": len(response.content),
                "content_type": response.headers.get("content-type"),
            }
        )
        page = response.text
        for block in re.findall(r"<script[^>]*>(.*?)</script>", page, re.S | re.I):
            block = html_module.unescape(block.strip())
            if not block or "RAW_FABRID" not in block:
                continue
            try:
                payload = json.loads(block)
            except Exception:
                continue
            file_object = _find_zip_file(payload)
            if file_object:
                target = _download_target(file_object, diagnostics, "page_json")
                if target:
                    benchmark.log("RAW-FABRID metadata resolved through page JSON")
                    return target

        for match in re.finditer(r"RAW_FABRID\\?\.zip", page, re.I):
            region = page[max(0, match.start() - 2500) : match.end() + 2500]
            identifiers = re.findall(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                region,
                re.I,
            )
            if identifiers:
                file_id = identifiers[-1]
                url = (
                    f"https://api.data.mendeley.com/datasets/{DATASET_ID}/files/"
                    f"{file_id}/file_downloaded?version={VERSION}"
                )
                benchmark.log("RAW-FABRID file id resolved through page source")
                return url, {
                    "source": "page_regex",
                    "file_id": file_id,
                    "diagnostics": diagnostics,
                }
    except Exception as error:
        diagnostics.append(
            {"url": page_url, "error": f"{type(error).__name__}: {error}"}
        )

    output = benchmark.O / "mendeley_resolution_diagnostics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    raise RuntimeError(
        "RAW-FABRID public file metadata could not be resolved. "
        f"Diagnostics written to {output}."
    )


benchmark.mendeley_url = resolve_mendeley_url
benchmark.main()
