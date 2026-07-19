from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import tarfile
from collections import deque
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from pypdf import PdfReader

UA = "ADIM-01E-0O-B1-R1/1.0"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(session: requests.Session, url: str, limit: int = 100_000_000):
    record = {"url": url, "ok": False}
    try:
        with session.get(url, timeout=60, stream=True, allow_redirects=True) as response:
            record.update(
                status_code=response.status_code,
                final_url=response.url,
                content_type=response.headers.get("content-type", ""),
            )
            response.raise_for_status()
            buffer = bytearray()
            for block in response.iter_content(1024 * 1024):
                if block:
                    buffer.extend(block)
                if len(buffer) > limit:
                    raise RuntimeError(f"response exceeded {limit} bytes")
            data = bytes(buffer)
            record.update(ok=True, size_bytes=len(data), sha256=sha256(data))
            return data, record
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        return None, record


def extract_pdf_text(data: bytes, pages: int = 120) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:pages])
    except Exception:
        return ""


def html_links(base: str, content: str) -> list[str]:
    links = set()
    for raw in re.findall(r"(?:href|src)=[\"']([^\"']+)", content, flags=re.I):
        value = raw.replace("&amp;", "&").strip()
        if value.startswith(("javascript:", "mailto:", "#")):
            continue
        links.add(urljoin(base, value))
    return sorted(links)


def normalized_name_evidence(text: str, name: str) -> bool:
    value = text.lower().replace("\n", " ")
    value = re.sub(r"\s+", " ", value)
    substitutions = {
        "christina büsing": [r"christina\s+b(?:ü|u|¨\s*u|\\\"u)sing"],
        "nils nießen": [r"nils\s+nie(?:ß|ss|ÃŸ|\\ss)en"],
    }
    patterns = substitutions.get(name.lower(), [re.escape(name.lower())])
    return any(re.search(pattern, value, flags=re.I) for pattern in patterns)


def resolve_friesen(session: requests.Session, incoming: Path, output: Path):
    records = []
    api_data, api_record = fetch(
        session,
        "https://export.arxiv.org/api/query?id_list=2308.00420",
        2_000_000,
    )
    records.append(api_record)
    arxiv_authors = []
    if api_data:
        (output / "friesen_arxiv_api.xml").write_bytes(api_data)
        arxiv_authors = [
            re.sub(r"\s+", " ", value).strip()
            for value in re.findall(
                r"<name>(.*?)</name>",
                api_data.decode(errors="replace"),
                flags=re.S,
            )
        ]

    datacite_data, datacite_record = fetch(
        session,
        "https://api.datacite.org/dois/10.48550/arXiv.2308.00420",
        5_000_000,
    )
    records.append(datacite_record)
    datacite_authors = []
    if datacite_data:
        (output / "friesen_datacite.json").write_bytes(datacite_data)
        try:
            datacite_authors = [
                item.get("name", "")
                for item in json.loads(datacite_data)["data"]["attributes"].get(
                    "creators", []
                )
            ]
        except Exception:
            pass

    pdf_text = "\n".join(
        (page.extract_text() or "")
        for page in PdfReader(str(incoming / "friesen_2308.00420.pdf")).pages[:2]
    )
    five = [
        "Nadine Friesen",
        "Tim Sander",
        "Christina Büsing",
        "Karl Nachtigall",
        "Nils Nießen",
    ]
    pdf_hits = [name for name in five if normalized_name_evidence(pdf_text, name)]

    tex_hits = set()
    author_tex_bytes = b""
    with tarfile.open(incoming / "friesen_2308.00420_source.tar", "r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.lower().endswith(".tex"):
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            data = handle.read()
            text = data.decode("utf-8", errors="replace")
            for name in five:
                variants = [name, name.replace("ü", r'\"u'), name.replace("ß", r"\ss")]
                if any(value.lower() in text.lower() for value in variants):
                    tex_hits.add(name)
            if member.name.endswith("author.tex"):
                author_tex_bytes = data
                (output / "friesen_author.tex").write_bytes(data)

    manuscript_five = set(tex_hits) == set(five)
    repository_four = (
        len(arxiv_authors) == 4
        and len(datacite_authors) == 4
        and not any("Büsing" in value or "Busing" in value for value in arxiv_authors)
    )
    resolution = manuscript_five and repository_four
    result = {
        "arxiv_api_authors": arxiv_authors,
        "datacite_authors": datacite_authors,
        "pdf_normalized_byline_hits": pdf_hits,
        "source_archive_author_hits": sorted(tex_hits),
        "author_tex_sha256": sha256(author_tex_bytes) if author_tex_bytes else None,
        "repository_metadata_record": "FOUR_AUTHORS",
        "manuscript_and_source_record": "FIVE_AUTHORS" if manuscript_five else "NOT_PROVEN",
        "resolution_status": "RESOLVED_AS_DUAL_RECORD" if resolution else "UNRESOLVED",
        "citation_policy": (
            "Cite the five-author manuscript/source byline for the work; preserve the four-author arXiv/DataCite metadata as a separately documented metadata defect."
            if resolution
            else "Do not normalize the author list."
        ),
        "network_records": records,
    }
    write_json(output / "friesen_author_resolution.json", result)
    (output / "friesen_pdf_first_two_pages.txt").write_text(pdf_text, encoding="utf-8")
    return result


def classify_highland_pdf(data: bytes):
    if not data.startswith(b"%PDF-"):
        return None
    text = extract_pdf_text(data, 160)
    low = re.sub(r"\s+", " ", text.lower())
    title = all(term in low for term in ("roads", "transport", "guidelines"))
    section = bool(re.search(r"5\s*\.\s*3\s*\.\s*6", low))
    passing = "passing place" in low
    return {
        "title_terms_present": title,
        "section_5_3_6_present": section,
        "passing_place_present": passing,
        "qualifies": title and section and passing,
        "text_excerpt": low[:1500],
    }


def discover_highland(session: requests.Session, output: Path):
    records = []
    candidates = {
        "https://www.highland.gov.uk/downloads/file/5272/roads_and_transport_guidelines_for_new_developments",
        "https://www.highland.gov.uk/download/downloads/id/5272/roads_and_transport_guidelines_for_new_developments.pdf",
        "https://www.highland.gov.uk/download/downloads/id/5272/roads_and_transport_guidelines_for_new_developments",
    }

    sitemap, sitemap_record = fetch(session, "https://www.highland.gov.uk/sitemap.xml", 10_000_000)
    records.append(sitemap_record)
    if sitemap:
        (output / "highland_sitemap.xml").write_bytes(sitemap)
        text = sitemap.decode(errors="replace")
        urls = re.findall(r"<loc>(.*?)</loc>", text, flags=re.S)
        relevant = [
            value.strip()
            for value in urls
            if any(
                token in value.lower()
                for token in ("road", "transport", "guideline", "development")
            )
        ]
        (output / "highland_relevant_sitemap_urls.txt").write_text(
            "\n".join(relevant), encoding="utf-8"
        )
        candidates.update(relevant[:500])

    verified = []
    visited = set()
    queue = deque(sorted(candidates))
    page_budget = 650
    while queue and len(visited) < page_budget:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        data, record = fetch(session, url, 50_000_000)
        records.append(record)
        if not data:
            continue
        classification = classify_highland_pdf(data)
        if classification:
            record.update(classification)
            if classification["qualifies"]:
                path = output / f"highland_guideline_candidate_{len(verified)+1}.pdf"
                path.write_bytes(data)
                record.update(local_path=str(path), local_sha256=sha256(data))
                verified.append(record)
            continue

        content_type = record.get("content_type", "").lower()
        if "html" in content_type or data[:20].lower().startswith((b"<!doctype", b"<html")):
            html = data.decode(errors="replace")
            for link in html_links(record.get("final_url", url), html):
                lower = link.lower()
                if (
                    urlparse(link).netloc.endswith("highland.gov.uk")
                    and any(token in lower for token in ("road", "transport", "guideline", "download", ".pdf"))
                ):
                    queue.append(link)

    result = {
        "candidate_seed_count": len(candidates),
        "visited_url_count": len(visited),
        "canonical_guideline_acquired": bool(verified),
        "canonical_candidates": verified,
        "status": "ACQUIRED_VERIFIED_HASHED" if verified else "NOT_ACQUIRED",
        "records": records,
    }
    write_json(output / "highland_guideline_discovery.json", result)
    return result


def direct_location_evidence(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text)
    return bool(
        re.search(
            r"(optimal|optimisation|optimization|mixed integer|integer programming).{0,500}(passing (bay|loop|siding)|crossing loop|sidings).{0,500}(location|locations|placement|number)",
            normalized,
            flags=re.I | re.S,
        )
        or re.search(
            r"(passing (bay|loop|siding)|crossing loop|sidings).{0,500}(optimal|optimisation|optimization|mixed integer|integer programming).{0,500}(location|locations|placement|number)",
            normalized,
            flags=re.I | re.S,
        )
    )


def crawl_for_pdf(session, start_url: str, records: list, max_pages: int = 30):
    queue = deque([start_url])
    visited = set()
    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        data, record = fetch(session, url, 180_000_000)
        record["crawl_root"] = start_url
        records.append(record)
        if not data:
            continue
        if data.startswith(b"%PDF-"):
            return data, record, sorted(visited)
        content_type = record.get("content_type", "").lower()
        if "html" not in content_type and not data[:20].lower().startswith((b"<!doctype", b"<html")):
            continue
        html = data.decode(errors="replace")
        links = html_links(record.get("final_url", url), html)
        ranked = sorted(
            links,
            key=lambda value: (
                0 if any(token in value.lower() for token in ("download", "bitstream", ".pdf", "fulltext")) else 1,
                len(value),
            ),
        )
        for link in ranked[:80]:
            lower = link.lower()
            if any(token in lower for token in ("download", "bitstream", ".pdf", "fulltext", "handle", "item")):
                queue.append(link)
    return None, None, sorted(visited)


def discover_baseline(session: requests.Session, output: Path):
    records = []
    targets = [
        {
            "title": "Capacity evaluation and infrastructure planning techniques for heterogeneous railway traffic under structured, mixed, and flexible operation",
            "year": 2017,
            "identifier": "hdl:2142/98121",
            "start_urls": [
                "https://hdl.handle.net/2142/98121",
                "https://www.ideals.illinois.edu/items/113036",
                "https://www.ideals.illinois.edu/handle/2142/98121",
            ],
            "role": "source-complete dissertation with optimal number and locations of passing sidings",
        },
        {
            "title": "Optimising passing bay locations and vehicle schedules in underground mines",
            "year": 2012,
            "identifier": "doi:10.1057/jors.2012.42",
            "start_urls": [
                "https://doi.org/10.1057/jors.2012.42",
                "https://api.openalex.org/works/https://doi.org/10.1057/jors.2012.42",
                "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1057/jors.2012.42?fields=title,authors,year,abstract,externalIds,openAccessPdf,url",
            ],
            "role": "direct road-like underground-mine passing-bay MIP",
        },
        {
            "title": "Optimization of Siding Location for Single-Track Lines",
            "year": 2014,
            "identifier": "doi:10.3141/2448-09",
            "start_urls": [
                "https://doi.org/10.3141/2448-09",
                "https://api.openalex.org/works/https://doi.org/10.3141/2448-09",
                "https://api.semanticscholar.org/graph/v1/paper/DOI:10.3141/2448-09?fields=title,authors,year,abstract,externalIds,openAccessPdf,url",
            ],
            "role": "direct single-track passing-siding location optimizer",
        },
    ]

    acquired = []
    bibliographic = []
    for target in targets:
        target_record = {**target, "attempts": []}
        for start_url in target["start_urls"]:
            data, record, visited = crawl_for_pdf(session, start_url, records)
            target_record["attempts"].append(
                {
                    "start_url": start_url,
                    "visited_url_count": len(visited),
                    "pdf_recovered": bool(data),
                    "visited_urls": visited,
                }
            )
            if not data:
                continue
            text = extract_pdf_text(data, 250)
            qualifies = direct_location_evidence(text)
            path = output / f"direct_baseline_candidate_{len(acquired)+1}.pdf"
            path.write_bytes(data)
            candidate = {
                **target,
                "retrieval_start_url": start_url,
                "final_url": record.get("final_url") if record else None,
                "size_bytes": len(data),
                "sha256": sha256(data),
                "pdf_signature": True,
                "direct_location_evidence": qualifies,
                "local_path": str(path),
                "text_keyword_excerpt": re.sub(r"\s+", " ", text)[:3000],
            }
            acquired.append(candidate)
            target_record["acquired_candidate"] = candidate
            break
        bibliographic.append(target_record)

    qualifying = [item for item in acquired if item["direct_location_evidence"]]
    result = {
        "target_count": len(targets),
        "bibliographic_records": bibliographic,
        "acquired_pdf_candidates": acquired,
        "qualifying_direct_sources": qualifying,
        "direct_passing_bay_optimization_source_acquired": bool(qualifying),
        "status": "ACQUIRED_VERIFIED_HASHED" if qualifying else "NOT_ACQUIRED",
        "network_records": records,
    }
    write_json(output / "direct_baseline_discovery.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "b1_derived"
    output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    result = {
        "friesen": resolve_friesen(session, root / "incoming", output),
        "highland": discover_highland(session, output),
        "baseline": discover_baseline(session, output),
    }
    write_json(output / "source_repair_summary.json", result)
    print(
        json.dumps(
            {
                "friesen": result["friesen"]["resolution_status"],
                "highland": result["highland"]["status"],
                "baseline": result["baseline"]["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
