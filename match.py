import argparse
import json
import os
import re
import sys
import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from rapidfuzz import fuzz

_non_alnum = re.compile(r"[^a-z0-9+#.\-\s]")


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def tokenize_for_fuzz(text: str) -> str:
    text = (text or "").lower()
    text = _non_alnum.sub(" ", text)
    return " ".join(t for t in text.split() if len(t) > 1)


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jobs(local: str | None, url: str | None, here: Path) -> list[dict[str, Any]]:
    if local:
        with open(local, "r", encoding="utf-8") as f:
            return json.load(f)
    if url:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()
    # default to sample from JS tool to avoid duplication
    with open(here.parent / "resume" / "jobs_sample.json", "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_serpapi_google_jobs(query: str, location: str | None, api_key: str, fetch_limit: int) -> list[dict[str, Any]]:
    params = {
        "engine": "google_jobs",
        "q": query,
        "hl": "en",
        "api_key": api_key,
    }
    if location:
        params["location"] = location
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("jobs_results", []) or []

    results: list[dict[str, Any]] = []
    for it in items[:fetch_limit]:
        title = it.get("title") or ""
        company = it.get("company_name") or it.get("company") or ""
        loc = it.get("location") or ""
        desc = it.get("description") or ""
        url = None
        # Prefer direct apply_links if present
        apply_options = it.get("apply_options") or []
        if apply_options and isinstance(apply_options, list):
            # pick first
            url = apply_options[0].get("link") or apply_options[0].get("apply_link")
        if not url:
            related = it.get("related_links") or []
            if related:
                url = related[0].get("link")
        if not url:
            url = it.get("job_id")  # fallback id reference
        results.append({
            "title": title,
            "company": company,
            "location": loc,
            "description": desc,
            "url": url,
            "source": "serpapi_google_jobs"
        })
    return results


# ---------- Free sources (no API key required) ----------

def _query_match(text: str, query: str) -> bool:
    """Return True if text matches query.
    - Supports OR terms with '|' (any token match).
    - Otherwise requires at least 50% of query tokens to be present (lenient).
    """
    if not query:
        return True
    hay = tokenize_for_fuzz(text).split()
    hay_set = set(hay)

    # OR support with '|'
    if '|' in query:
        ors = [t.strip() for t in query.split('|') if t.strip()]
        return any(tokenize_for_fuzz(term) in ' '.join(hay) or any(tok in hay_set for tok in tokenize_for_fuzz(term).split()) for term in ors)

    q_tokens = [t for t in tokenize_for_fuzz(query).split() if t]
    if not q_tokens:
        return True
    matched = sum(1 for t in q_tokens if t in hay_set)
    return matched >= max(1, int(len(q_tokens) * 0.5))


def fetch_remotive(query: str | None, fetch_limit: int) -> list[dict[str, Any]]:
    # Docs: https://remotive.com/api/remote-jobs
    params: dict[str, Any] = {}
    if query:
        params["search"] = query
    resp = requests.get("https://remotive.com/api/remote-jobs", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    jobs = data.get("jobs", []) or []
    results: list[dict[str, Any]] = []
    for it in jobs:
        title = it.get("title") or ""
        company = it.get("company_name") or ""
        loc = it.get("candidate_required_location") or it.get("location") or "Remote"
        desc = it.get("description") or ""
        url = it.get("url") or ""
        results.append({
            "title": title,
            "company": company,
            "location": loc,
            "description": desc,
            "url": url,
            "source": "remotive"
        })
        if len(results) >= fetch_limit:
            break
    return results


def fetch_remoteok(query: str | None, fetch_limit: int) -> list[dict[str, Any]]:
    # Docs: https://remoteok.com/api
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JobMatcher/1.0)"}
    resp = requests.get("https://remoteok.com/api", headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    filtered: list[dict[str, Any]] = []
    unfiltered: list[dict[str, Any]] = []
    for it in data:
        # First element can be legal notice (dict with 'legal')
        if isinstance(it, dict) and it.get("position"):
            title = it.get("position") or ""
            company = it.get("company") or ""
            loc = it.get("location") or "Remote"
            desc = it.get("description") or ""
            url = it.get("url") or it.get("apply_url") or ""
            combined = f"{title}\n{company}\n{loc}\n{desc}"
            unfiltered.append({
                "title": title,
                "company": company,
                "location": loc,
                "description": desc,
                "url": url,
                "source": "remoteok"
            })
            if _query_match(combined, query or ""):
                filtered.append(unfiltered[-1])
    # Respect fetch_limit
    if filtered:
        return filtered[:fetch_limit]
    return unfiltered[:fetch_limit]


def fetch_arbeitnow(query: str | None, fetch_limit: int) -> list[dict[str, Any]]:
    # Docs: https://www.arbeitnow.com/api/job-board-api
    resp = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data", []) or []
    filtered: list[dict[str, Any]] = []
    unfiltered: list[dict[str, Any]] = []
    for it in items:
        title = it.get("title") or it.get("position") or ""
        company = it.get("company") or ""
        loc = it.get("location") or "Remote"
        desc = it.get("description") or ""
        url = it.get("url") or ""
        combined = f"{title}\n{company}\n{loc}\n{desc}"
        entry = {
            "title": title,
            "company": company,
            "location": loc,
            "description": desc,
            "url": url,
            "source": "arbeitnow"
        }
        unfiltered.append(entry)
        if _query_match(combined, query or ""):
            filtered.append(entry)
    if filtered:
        return filtered[:fetch_limit]
    return unfiltered[:fetch_limit]


# ---------- Company career sources (no auth) ----------
def fetch_lever(companies: list[str], fetch_limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for slug in companies:
        try:
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            posts = resp.json()
            for p in posts:
                title = p.get("text") or p.get("title") or ""
                company = p.get("company") or slug
                loc = (p.get("categories") or {}).get("location") or ""
                desc = p.get("descriptionPlain") or ""
                job_url = p.get("hostedUrl") or p.get("applyUrl") or (p.get("urls", {}) or {}).get("list") or ""
                results.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "description": desc,
                    "url": job_url,
                    "source": f"lever:{slug}"
                })
                if len(results) >= fetch_limit:
                    return results
        except Exception:
            continue
    return results


def fetch_greenhouse(companies: list[str], fetch_limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for slug in companies:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", [])
            for j in jobs:
                title = j.get("title") or ""
                company = slug
                loc = (j.get("location") or {}).get("name") or ""
                job_url = j.get("absolute_url") or ""
                desc = ""
                try:
                    job_id = j.get("id")
                    if job_id:
                        detail_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}?content=true"
                        dr = requests.get(detail_url, timeout=30)
                        if dr.ok:
                            dj = dr.json()
                            desc = dj.get("content") or ""
                except Exception:
                    pass
                results.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "description": desc,
                    "url": job_url,
                    "source": f"greenhouse:{slug}"
                })
                if len(results) >= fetch_limit:
                    return results
        except Exception:
            continue
    return results


FREE_SOURCES = {
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "arbeitnow": fetch_arbeitnow,
}

COMPANY_SOURCES = {
    "lever": fetch_lever,
    "greenhouse": fetch_greenhouse,
}


def score_job(job: dict[str, Any], resume_text: str) -> float:
    title = job.get("title", "")
    fields = "\n".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("description", ""),
    ])
    # token-set fuzzy similarity
    sim = fuzz.token_set_ratio(tokenize_for_fuzz(resume_text), tokenize_for_fuzz(fields))
    # boost relevant titles
    if re.search(r"mlops|machine\s+learning|data\s+engineer|full\s*stack|python", title.lower()):
        sim += 10
    return float(sim)


def resolve_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    # Normalize common fields
    fetch = cfg.get("fetch", {})
    mode = fetch.get("mode")  # "free" | "serpapi" | "json" | "url" | "company"
    source = fetch.get("source")  # e.g., remotive
    query = fetch.get("query")
    location = fetch.get("location")
    jobs_path = fetch.get("jobs")
    jobs_url = fetch.get("jobs_url")
    serpapi_key = fetch.get("serpapi_key") or os.getenv("SERPAPI_KEY")
    company_source = fetch.get("company_source")
    companies = fetch.get("companies") or []
    # optional combined options
    free_options = cfg.get("free_options", {})
    company_options = cfg.get("company_options", {})
    run_both = bool(cfg.get("run_both", False))

    return {
        "resume": cfg.get("resume"),
        "top": int(cfg.get("top", 10)),
        "mode": mode,
        "source": source,
        "query": query,
        "location": location,
        "jobs": jobs_path,
        "jobs_url": jobs_url,
        "serpapi_key": serpapi_key,
        "company_source": company_source,
        "companies": companies,
        "output": cfg.get("output", {}),
        "free_options": free_options,
        "company_options": company_options,
        "run_both": run_both,
    }


def _arg_present(flag: str) -> bool:
    return any(a == flag or a.startswith(flag + "=") for a in sys.argv)


def write_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    fields = ["title", "company", "location", "score", "url", "source", "description"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "title": r.get("title", ""),
                "company": r.get("company", ""),
                "location": r.get("location", ""),
                "score": r.get("score", ""),
                "url": r.get("url", ""),
                "source": r.get("source", ""),
                "description": (r.get("description", "") or "").replace("\r", " ").replace("\n", " ")
            })


def main() -> None:
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Score and list top matching jobs for a given resume.")
    parser.add_argument("--resume", default=str(here.parent / "resume" / "input" / "resume.txt"), help="Path to resume text file")
    parser.add_argument("--jobs", default=None, help="Path to jobs JSON (array)")
    parser.add_argument("--jobs-url", dest="jobs_url", default=None, help="HTTP URL returning JSON jobs array")
    parser.add_argument("--top", type=int, default=10, help="Top N results")
    parser.add_argument("--fetch-limit", type=int, default=200, help="Max number of jobs to fetch before scoring")
    # Config support
    parser.add_argument("--config", default=None, help="Path to config JSON (overrides defaults)")
    # Free sources (no API key)
    parser.add_argument("--free-source", choices=list(FREE_SOURCES.keys()), default=None, help="Use a free jobs source (no API key)")
    # SerpAPI options (Google Jobs)
    parser.add_argument("--serpapi-key", default=os.getenv("SERPAPI_KEY"), help="SerpAPI key (optional)")
    parser.add_argument("--query", default=None, help="Search query, e.g., 'Python MLOps Engineer' or 'python|mlops|data'")
    parser.add_argument("--location", default=None, help="Search location (used by some sources)")
    # Company careers
    parser.add_argument("--company-source", choices=list({"lever", "greenhouse"}), default=None, help="Company careers source")
    parser.add_argument("--companies", default=None, help="Comma-separated company slugs (e.g., 'openai,databricks')")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    parser.add_argument("--out", default=str(here / "output" / f"matched_jobs_{ts}.json"), help="Output JSON path")
    parser.add_argument("--csv-out", default=None, help="Optional CSV output path; defaults to same as --out with .csv suffix")
    parser.add_argument("--save-fetched", action="store_true", help="Also save all fetched jobs to JSON and CSV")
    parser.add_argument("--run-both", action="store_true", help="Fetch from both free_options and company_options and combine")
    args = parser.parse_args()

    # Load and merge config if provided (or if default exists)
    cfg_path = Path(args.config) if args.config else (here / "config.json")
    cfg_data: dict[str, Any] | None = None
    if cfg_path.exists():
        try:
            cfg_data = load_json(cfg_path)
        except Exception:
            cfg_data = None
    resolved_cfg: dict[str, Any] = resolve_from_config(cfg_data) if cfg_data else {}

    # Merge precedence with safe fallback:
    # 1) if --resume explicitly passed, use it
    # 2) else if config has resume, use it
    # 3) else try common defaults in order
    resume_path_candidate = args.resume if _arg_present("--resume") else (resolved_cfg.get("resume") or None)
    candidates = [
        resume_path_candidate,
        str(here / "resume.txt"),
        str(here / "input" / "resume.txt"),
        str(here.parent / "resume" / "input" / "resume.txt"),
    ]
    candidates = [c for c in candidates if c]
    resume_file: Path | None = None
    for c in candidates:
        p = Path(c)
        if p.exists():
            resume_file = p
            break
    if not resume_file:
        raise SystemExit(
            "Resume file not found. Set `resume` in config.json or pass --resume <path>. "
            "Tried: " + ", ".join(candidates)
        )

    top_n = args.top if args.top else int(resolved_cfg.get("top", 10))

    # Source selection
    free_source = args.free_source or (resolved_cfg.get("source") if resolved_cfg.get("mode") == "free" else None)
    query = args.query or resolved_cfg.get("query")
    location = args.location or resolved_cfg.get("location")
    serpapi_key = args.serpapi_key or resolved_cfg.get("serpapi_key")
    jobs_arg = args.jobs or resolved_cfg.get("jobs")
    jobs_url_arg = args.jobs_url or resolved_cfg.get("jobs_url")
    company_source = args.company_source or (resolved_cfg.get("company_source") if resolved_cfg.get("mode") == "company" else None)
    companies_arg = args.companies or None
    if not companies_arg:
        cfg_companies = resolved_cfg.get("companies") or []
    else:
        cfg_companies = [c.strip() for c in companies_arg.split(",") if c.strip()]

    # Combined options from config
    free_opts = resolved_cfg.get("free_options") or {}
    company_opts = resolved_cfg.get("company_options") or {}
    run_both = args.run_both or bool(resolved_cfg.get("run_both"))

    # Output handling (configurable dir/prefix)
    out_cfg = resolved_cfg.get("output", {}) if resolved_cfg else {}
    out_path = args.out
    if out_cfg and not _arg_present("--out"):
        out_dir = out_cfg.get("dir")
        prefix = out_cfg.get("prefix", "matched_jobs")
        if out_dir:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = str(Path(here / out_dir / f"{prefix}_{stamp}.json"))

    resume_text = read_text(resume_file)

    # Fetch jobs according to chosen source(s)
    fetched: list[dict[str, Any]] = []

    def _dedupe_by_url(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for it in items:
            key = (it.get("url") or f"{it.get('title','')}|{it.get('company','')}|{it.get('location','')}")
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out

    if run_both:
        # Company block
        comp_src = company_source or company_opts.get("company_source")
        comp_companies = cfg_companies or company_opts.get("companies") or []
        comp_query = query or company_opts.get("query")
        if comp_src and comp_companies:
            comp_fetcher = COMPANY_SOURCES.get(comp_src)
            if not comp_fetcher:
                raise SystemExit(f"Unknown company source: {comp_src}")
            fetched += comp_fetcher(comp_companies, args.fetch_limit)
        # Free block
        free_src = free_source or free_opts.get("source")
        free_query = query or free_opts.get("query")
        if free_src and free_query is not None:
            free_fetcher = FREE_SOURCES.get(free_src)
            if not free_fetcher:
                raise SystemExit(f"Unknown free source: {free_src}")
            fetched += free_fetcher(free_query, args.fetch_limit)
        fetched = _dedupe_by_url(fetched)
    else:
        if company_source and cfg_companies:
            fetcher = COMPANY_SOURCES.get(company_source)
            if not fetcher:
                raise SystemExit(f"Unknown company source: {company_source}")
            fetched = fetcher(cfg_companies, args.fetch_limit)
        elif free_source and query is not None:
            fetcher = FREE_SOURCES.get(free_source)
            if not fetcher:
                raise SystemExit(f"Unknown free source: {free_source}")
            fetched = fetcher(query, args.fetch_limit)
        elif serpapi_key and query:
            fetched = fetch_serpapi_google_jobs(query, location, serpapi_key, args.fetch_limit)
        else:
            fetched = load_jobs(jobs_arg, jobs_url_arg, here)
            if isinstance(fetched, dict) and 'items' in fetched:
                fetched = fetched['items']  # normalize
            if not isinstance(fetched, list):
                fetched = []
            fetched = fetched[: args.fetch_limit]

    # Score and select
    scored = []
    for job in fetched:
        s = score_job(job, resume_text)
        scored.append({**job, "score": round(s, 2)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: top_n]

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(top, f, indent=2)

    # CSV path for top N
    csv_path = Path(args.csv_out) if args.csv_out else out_file.with_suffix('.csv')
    write_csv(top, csv_path)

    # Save fetched list (JSON/CSV) if requested
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fetched_json = out_file.parent / f"fetched_jobs_{stamp}.json"
    fetched_csv = out_file.parent / f"fetched_jobs_{stamp}.csv"
    if args.save_fetched:
        with open(fetched_json, "w", encoding="utf-8") as f:
            json.dump(fetched, f, indent=2)
        # add dummy score column for CSV uniformity
        fetched_rows = [{**j, "score": ""} for j in fetched]
        write_csv(fetched_rows, fetched_csv)

    # Always also produce top-50 alongside configured top
    top50 = scored[:50]
    top50_json = out_file.parent / f"top50_jobs_{stamp}.json"
    top50_csv = out_file.parent / f"top50_jobs_{stamp}.csv"
    with open(top50_json, "w", encoding="utf-8") as f:
        json.dump(top50, f, indent=2)
    write_csv(top50, top50_csv)

    print("Top matches:")
    for j in top:
        line = f"- [{j['score']}] {j.get('title','')} @ {j.get('company','')} ({j.get('location','')})"
        if j.get("url"):
            line += f" - {j['url']}"
        print(line)
    print("Saved to:", os.path.abspath(out_file))
    print("CSV saved to:", os.path.abspath(csv_path))
    if args.save_fetched:
        print("Fetched JSON:", os.path.abspath(fetched_json))
        print("Fetched CSV:", os.path.abspath(fetched_csv))
    print("Top50 JSON:", os.path.abspath(top50_json))
    print("Top50 CSV:", os.path.abspath(top50_csv))


if __name__ == "__main__":
    main()
