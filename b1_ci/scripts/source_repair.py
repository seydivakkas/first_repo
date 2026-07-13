from __future__ import annotations

import argparse, hashlib, io, json, re, tarfile, time
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from pypdf import PdfReader

UA = "ADIM-01E-0O-B1/1.0"


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(session, url, limit=80_000_000):
    rec = {"url": url, "ok": False}
    try:
        with session.get(url, timeout=45, stream=True, allow_redirects=True) as r:
            rec.update(status_code=r.status_code, final_url=r.url, content_type=r.headers.get("content-type", ""))
            r.raise_for_status()
            buf = bytearray()
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    buf.extend(chunk)
                if len(buf) > limit:
                    raise RuntimeError(f"response exceeded {limit} bytes")
            data = bytes(buf)
            rec.update(ok=True, size_bytes=len(data), sha256=sha256_bytes(data))
            return data, rec
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return None, rec


def pdf_text(data: bytes, pages=40):
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:pages])
    except Exception:
        return ""


def tex_author_evidence(path: Path):
    names = ["Nadine Friesen", "Tim Sander", "Christina Büsing", "Karl Nachtigall", "Nils Nießen"]
    result = {"name_hits": {}, "author_blocks": [], "tex_files": []}
    with tarfile.open(path, "r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.lower().endswith((".tex", ".txt")):
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            text = handle.read().decode("utf-8", errors="replace")
            result["tex_files"].append(member.name)
            low = text.lower()
            for name in names:
                variants = [name, name.replace("ü", r'\"u'), name.replace("ß", "ss")]
                if any(v.lower() in low for v in variants):
                    result["name_hits"].setdefault(name, []).append(member.name)
            for m in re.finditer(r"\\author(?:\[[^\]]*\])?\s*\{(.{0,2500}?)\}", text, re.S):
                result["author_blocks"].append({"file": member.name, "raw": re.sub(r"\s+", " ", m.group(1))[:2500]})
    return result


def resolve_friesen(session, incoming: Path, output: Path):
    records, arxiv_authors, datacite_authors = [], [], []
    data, rec = fetch(session, "https://export.arxiv.org/api/query?id_list=2308.00420", 2_000_000)
    records.append(rec)
    if data:
        (output / "friesen_arxiv_api.xml").write_bytes(data)
        arxiv_authors = [re.sub(r"\s+", " ", x).strip() for x in re.findall(r"<name>(.*?)</name>", data.decode(errors="replace"), re.S)]
    data, rec = fetch(session, "https://api.datacite.org/dois/10.48550/arXiv.2308.00420", 5_000_000)
    records.append(rec)
    if data:
        (output / "friesen_datacite.json").write_bytes(data)
        try:
            datacite_authors = [x.get("name", "") for x in json.loads(data)["data"]["attributes"].get("creators", [])]
        except Exception:
            pass
    pdf_first = PdfReader(str(incoming / "friesen_2308.00420.pdf")).pages[0].extract_text() or ""
    tex = tex_author_evidence(incoming / "friesen_2308.00420_source.tar")
    five = ["Nadine Friesen", "Tim Sander", "Christina Büsing", "Karl Nachtigall", "Nils Nießen"]
    pdf_hits = [x for x in five if x in pdf_first]
    tex_hits = [x for x in five if x in tex["name_hits"]]
    manuscript_five = sorted(pdf_hits) == sorted(five) and sorted(tex_hits) == sorted(five)
    repository_four = len(arxiv_authors) == 4 and "Christina Büsing" not in arxiv_authors
    result = {
        "arxiv_api_authors": arxiv_authors,
        "datacite_authors": datacite_authors,
        "pdf_byline_name_hits": pdf_hits,
        "source_archive_name_hits": tex_hits,
        "source_archive_evidence": tex,
        "network_records": records,
        "resolution_status": "RESOLVED_AS_DUAL_RECORD" if manuscript_five and repository_four else "UNRESOLVED",
        "citation_policy": "Use the five-author manuscript/source byline for paper-content attribution; preserve the four-author repository metadata as a separate defective metadata record." if manuscript_five and repository_four else "Do not normalize the author list.",
    }
    write_json(output / "friesen_author_resolution.json", result)
    (output / "friesen_pdf_first_page.txt").write_text(pdf_first, encoding="utf-8")
    return result


def links(base, html):
    return {urljoin(base, x.replace("&amp;", "&")) for x in re.findall(r"(?:href|src)=[\"']([^\"']+)", html, re.I)}


def discover_highland(session, output: Path):
    seeds = [
        "https://www.highland.gov.uk/sitemap.xml",
        "https://www.highland.gov.uk/sitemap_index.xml",
        "https://www.highland.gov.uk/downloads/search?search=Roads%20and%20Transport%20Guidelines%20for%20New%20Developments",
        "https://www.highland.gov.uk/site_search/results/?q=Roads%20and%20Transport%20Guidelines%20for%20New%20Developments",
        "https://web.archive.org/cdx/search/cdx?url=www.highland.gov.uk/*roads*transport*guidelines*&output=json&filter=statuscode:200&collapse=digest&fl=timestamp,original,statuscode,mimetype,digest&limit=5000",
        "https://web.archive.org/cdx/search/cdx?url=www.highland.gov.uk/*guidelines*new*developments*&output=json&filter=statuscode:200&collapse=digest&fl=timestamp,original,statuscode,mimetype,digest&limit=5000",
        "https://archive.org/advancedsearch.php?q=%22Roads+and+Transport+Guidelines+for+New+Developments%22&fl[]=identifier,title,description&rows=100&page=1&output=json",
    ]
    candidates, records = set(), []
    for url in seeds:
        data, rec = fetch(session, url, 30_000_000)
        records.append(rec)
        if not data:
            continue
        text = data.decode(errors="replace")
        candidates |= {u for u in links(rec.get("final_url", url), text) if "guideline" in u.lower() or u.lower().endswith(".pdf")}
        if "web.archive.org/cdx" in url:
            try:
                rows = json.loads(text)
                for row in rows[1:]:
                    candidates.add(f"https://web.archive.org/web/{row[0]}id_/{row[1]}")
            except Exception:
                pass
        if "archive.org/advancedsearch" in url:
            try:
                for doc in json.loads(text)["response"]["docs"]:
                    ident = doc["identifier"]
                    candidates.add(f"https://archive.org/download/{ident}/{ident}_text.pdf")
            except Exception:
                pass
    verified = []
    for url in sorted(candidates)[:250]:
        data, rec = fetch(session, url, 40_000_000)
        if not data:
            records.append(rec)
            continue
        text = pdf_text(data, 100) if data.startswith(b"%PDF-") else data.decode(errors="replace")
        low = text.lower()
        rec.update(
            pdf_signature=data.startswith(b"%PDF-"),
            title_score=sum(x in low for x in ("roads", "transport", "guidelines", "new", "developments")),
            contains_536=bool(re.search(r"5\s*\.\s*3\s*\.\s*6", text)),
            contains_passing_place="passing place" in low,
        )
        if rec["pdf_signature"] and rec["title_score"] >= 3 and rec["contains_536"] and rec["contains_passing_place"]:
            path = output / f"highland_guideline_candidate_{len(verified)+1}.pdf"
            path.write_bytes(data)
            rec.update(local_path=str(path), local_sha256=hashlib.sha256(data).hexdigest())
            verified.append(rec)
        records.append(rec)
    result = {
        "candidate_url_count": len(candidates),
        "canonical_guideline_acquired": bool(verified),
        "canonical_candidates": verified,
        "status": "ACQUIRED_VERIFIED_HASHED" if verified else "NOT_ACQUIRED",
        "records": records,
    }
    write_json(output / "highland_guideline_discovery.json", result)
    return result


def score(title, abstract):
    text = f"{title} {abstract}".lower()
    score = 0
    reasons = []
    for term in ("passing bay", "passing loop", "passing siding", "crossing loop", "siding location"):
        if term in text:
            score += 5; reasons.append(term)
    for term in ("optim", "location", "placement", "site selection", "network design"):
        if term in text:
            score += 2; reasons.append(term)
    if "scheduling" in text and not any(x in text for x in ("location", "placement", "site selection")):
        score -= 3; reasons.append("scheduling-only-penalty")
    return score, sorted(set(reasons))


def openalex_abstract(inv):
    if not inv: return ""
    return " ".join(w for _, w in sorted((i, w) for w, idxs in inv.items() for i in idxs))


def discover_baseline(session, output: Path):
    queries = [
        '"Optimisation of hauling schedules and passing bay locations"',
        '"Optimising passing bay locations and vehicle schedules"',
        'passing bay location optimization underground mine',
        'passing loop location optimization railway',
        'passing siding location optimization single track railway',
        'crossing loop placement network design',
        'siding location problem railway capacity expansion',
    ]
    pool, records = {}, []
    for query in queries:
        urls = [
            ("openalex", f"https://api.openalex.org/works?search={quote(query)}&per-page=100"),
            ("semantic", f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(query)}&limit=100&fields=title,authors,year,abstract,externalIds,openAccessPdf,url"),
            ("crossref", f"https://api.crossref.org/works?query.bibliographic={quote(query)}&rows=100"),
        ]
        for source, url in urls:
            data, rec = fetch(session, url, 30_000_000); rec.update(source=source, query=query); records.append(rec)
            if not data: continue
            try: obj = json.loads(data)
            except Exception: continue
            items = []
            if source == "openalex":
                for x in obj.get("results", []):
                    loc = x.get("best_oa_location") or x.get("primary_location") or {}
                    items.append({"id": x.get("id"), "title": x.get("title") or "", "abstract": openalex_abstract(x.get("abstract_inverted_index")), "year": x.get("publication_year"), "doi": x.get("doi"), "pdf_url": loc.get("pdf_url"), "landing_url": loc.get("landing_page_url")})
            elif source == "semantic":
                for x in obj.get("data", []):
                    items.append({"id": x.get("paperId"), "title": x.get("title") or "", "abstract": x.get("abstract") or "", "year": x.get("year"), "doi": (x.get("externalIds") or {}).get("DOI"), "pdf_url": (x.get("openAccessPdf") or {}).get("url"), "landing_url": x.get("url")})
            else:
                for x in obj.get("message", {}).get("items", []):
                    year = ((x.get("published-print") or x.get("published-online") or {}).get("date-parts") or [[None]])[0][0]
                    items.append({"id": x.get("DOI"), "title": " ".join(x.get("title", [])), "abstract": x.get("abstract") or "", "year": year, "doi": x.get("DOI"), "pdf_url": None, "landing_url": x.get("URL")})
            for item in items:
                item["source"] = source
                item["score"], item["score_reasons"] = score(item["title"], item["abstract"])
                key = str(item.get("doi") or item.get("id") or item["title"]).lower()
                if key not in pool or item["score"] > pool[key]["score"]:
                    pool[key] = item
        time.sleep(0.3)
    ranked = sorted(pool.values(), key=lambda x: (-x["score"], x["title"]))
    acquired = []
    for item in ranked[:40]:
        if item["score"] < 8 or not item.get("pdf_url"): continue
        data, rec = fetch(session, item["pdf_url"], 80_000_000); records.append({**rec, "candidate_title": item["title"]})
        if not data or not data.startswith(b"%PDF-"): continue
        text = pdf_text(data, 50)
        direct = bool(re.search(r"(location|placement|site selection).{0,150}(passing (bay|loop|siding)|crossing loop)|(passing (bay|loop|siding)|crossing loop).{0,150}(location|placement|site selection)", text, re.I | re.S))
        candidate = {**item, "direct_location_evidence": direct}
        path = output / f"direct_baseline_candidate_{len(acquired)+1}.pdf"
        path.write_bytes(data); candidate.update(local_path=str(path), local_sha256=hashlib.sha256(data).hexdigest())
        acquired.append(candidate)
    qualifying = [x for x in acquired if x["direct_location_evidence"]]
    result = {
        "queries": queries,
        "candidate_count": len(ranked),
        "ranked_candidates": ranked[:100],
        "acquired_pdf_candidates": acquired,
        "qualifying_direct_sources": qualifying,
        "direct_passing_bay_optimization_source_acquired": bool(qualifying),
        "status": "ACQUIRED_VERIFIED_HASHED" if qualifying else "NOT_ACQUIRED",
        "network_records": records,
    }
    write_json(output / "direct_baseline_discovery.json", result)
    return result


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True); args = ap.parse_args()
    root = args.root.resolve(); incoming = root / "incoming"; output = root / "b1_derived"; output.mkdir(parents=True, exist_ok=True)
    session = requests.Session(); session.headers.update({"User-Agent": UA})
    result = {
        "friesen": resolve_friesen(session, incoming, output),
        "highland": discover_highland(session, output),
        "baseline": discover_baseline(session, output),
    }
    write_json(output / "source_repair_summary.json", result)
    print(json.dumps({k: v.get("status", v.get("resolution_status")) for k, v in result.items()}, indent=2))


if __name__ == "__main__": main()
