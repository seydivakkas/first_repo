from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path

import requests
from pypdf import PdfReader


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def get(session: requests.Session, url: str, limit: int = 250_000_000):
    record = {"url": url, "ok": False}
    try:
        with session.get(url, timeout=60, stream=True, allow_redirects=True) as response:
            record.update(status_code=response.status_code, final_url=response.url, content_type=response.headers.get("content-type", ""))
            response.raise_for_status()
            buffer = bytearray()
            for block in response.iter_content(1024 * 1024):
                if block:
                    buffer.extend(block)
                if len(buffer) > limit:
                    raise RuntimeError(f"response exceeded {limit} bytes")
            data = bytes(buffer)
            record.update(ok=True, size_bytes=len(data), sha256=digest(data))
            return data, record
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        return None, record


def pdf_text(data: bytes, pages: int = 300) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:pages])


def acquire_highland(session: requests.Session, output: Path):
    url = "https://www.highland.gov.uk/downloads/file/6505/roads-and-transport-guidelines-for-new-developments"
    data, record = get(session, url, 80_000_000)
    result = {"record": record, "acquired": False}
    if not data or not data.startswith(b"%PDF-"):
        write_json(output / "highland_2013_guideline_acquisition.json", result)
        return result
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    normalized = re.sub(r"\s+", " ", text)
    requirements = {
        "title": "ROADS AND TRANSPORT GUIDELINES FOR NEW DEVELOPMENTS" in text.upper(),
        "date_may_2013": bool(re.search(r"May\s+2013", text, flags=re.I)),
        "section_5_3_6": bool(re.search(r"5\s*\.\s*3\s*\.\s*6\s+Single\s+Track\s+Access\s+Road", normalized, flags=re.I)),
        "figure_5_1": bool(re.search(r"Figure\s+5\s*\.\s*1\s+Single\s+Track\s+Access\s+Road\s+Passing\s+Place", normalized, flags=re.I)),
        "carriageway_3_3m": bool(re.search(r"carriageway\s+should\s+be\s+3\s*\.\s*3\s+metres\s+wide", normalized, flags=re.I)),
        "intervisible_150m": bool(re.search(r"inter-visible\s+passing\s+places.{0,160}maximum\s+distance\s+of\s+150\s+metres", normalized, flags=re.I)),
        "standard_and_large_options": bool(re.search(r"two\s+options.{0,200}standard\s+passing\s+place.{0,200}larger\s+size", normalized, flags=re.I)),
    }
    path = output / "HIGHLAND_ROADS_AND_TRANSPORT_GUIDELINES_MAY_2013.pdf"
    path.write_bytes(data)
    result.update(
        acquired=all(requirements.values()),
        local_path=str(path),
        local_sha256=digest(data),
        page_count=len(reader.pages),
        requirements=requirements,
        source_class="CANONICAL_HIGHLAND_2013_GUIDELINE",
    )
    write_json(output / "highland_2013_guideline_acquisition.json", result)
    return result


def href(obj, relation):
    return (((obj or {}).get("_links") or {}).get(relation) or {}).get("href")


def acquire_ideals(session: requests.Session, output: Path):
    records = []
    item = None
    endpoints = [
        "https://www.ideals.illinois.edu/server/api/core/items/search/byHandle?handle=2142/98121",
        "https://www.ideals.illinois.edu/server/api/discover/search/objects?query=dc.identifier.uri:%222142/98121%22&size=20",
    ]
    for url in endpoints:
        data, record = get(session, url, 20_000_000)
        records.append(record)
        if not data:
            continue
        try:
            obj = json.loads(data)
        except Exception:
            continue
        if obj.get("uuid"):
            item = obj
            break
        embedded = obj.get("_embedded") or {}
        for key in ("searchResult", "items"):
            values = embedded.get(key) or []
            for value in values:
                target = value.get("_embedded", {}).get("indexableObject") or value
                if target.get("uuid"):
                    item = target
                    break
            if item:
                break
        if item:
            break

    result = {"records": records, "item_found": bool(item), "pdf_acquired": False, "source_complete_direct_baseline": False}
    if not item:
        write_json(output / "ideals_direct_baseline_acquisition.json", result)
        return result

    result["item_uuid"] = item.get("uuid")
    result["item_name"] = item.get("name")
    bundles_url = href(item, "bundles") or f"https://www.ideals.illinois.edu/server/api/core/items/{item['uuid']}/bundles?size=100"
    data, record = get(session, bundles_url, 20_000_000)
    records.append(record)
    bundles = []
    if data:
        try:
            bundles = (json.loads(data).get("_embedded") or {}).get("bundles") or []
        except Exception:
            pass

    for bundle in bundles:
        if str(bundle.get("name", "")).upper() != "ORIGINAL":
            continue
        bitstreams_url = href(bundle, "bitstreams") or f"https://www.ideals.illinois.edu/server/api/core/bundles/{bundle['uuid']}/bitstreams?size=100"
        data, record = get(session, bitstreams_url, 20_000_000)
        records.append(record)
        bitstreams = []
        if data:
            try:
                bitstreams = (json.loads(data).get("_embedded") or {}).get("bitstreams") or []
            except Exception:
                pass
        for bitstream in bitstreams:
            name = str(bitstream.get("name", ""))
            content_url = href(bitstream, "content") or f"https://www.ideals.illinois.edu/server/api/core/bitstreams/{bitstream['uuid']}/content"
            payload, record = get(session, content_url, 250_000_000)
            records.append(record)
            if not payload or not payload.startswith(b"%PDF-"):
                continue
            text = pdf_text(payload, 350)
            normalized = re.sub(r"\s+", " ", text)
            title_match = "Capacity evaluation and infrastructure planning techniques" in normalized
            direct = bool(re.search(r"optimal\s+number\s+and\s+locations\s+of\s+passing\s+sidings", normalized, flags=re.I))
            path = output / "UIUC_CAPACITY_EVALUATION_PASSING_SIDING_DISSERTATION.pdf"
            path.write_bytes(payload)
            result.update(
                pdf_acquired=True,
                source_complete_direct_baseline=bool(title_match and direct),
                bitstream_name=name,
                bitstream_uuid=bitstream.get("uuid"),
                local_path=str(path),
                local_sha256=digest(payload),
                size_bytes=len(payload),
                page_count=len(PdfReader(io.BytesIO(payload)).pages),
                title_match=title_match,
                direct_location_evidence=direct,
                content_url=content_url,
            )
            write_json(output / "ideals_direct_baseline_acquisition.json", result)
            return result

    write_json(output / "ideals_direct_baseline_acquisition.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "ADIM-01E-0O-B1-R2/1.0", "Accept": "application/json, application/pdf, text/html;q=0.8"})
    highland = acquire_highland(session, args.output)
    ideals = acquire_ideals(session, args.output)
    gate = {
        "canonical_highland_2013_guideline_acquired": bool(highland.get("acquired")),
        "source_complete_direct_passing_siding_baseline_acquired": bool(ideals.get("source_complete_direct_baseline")),
        "baseline_implementation_authorization": False,
        "replication_authorization": False,
        "manuscript_rewrite_authorization": False,
    }
    write_json(args.output / "B1_R2_TARGETED_GATE.json", gate)
    print(json.dumps(gate, indent=2))


if __name__ == "__main__":
    main()
