import argparse
import json
import os
import re
import sys
import csv
from datetime import datetime
from urllib.parse import urljoin, urlparse
from pathlib import Path
from typing import Any

import requests
from rapidfuzz import fuzz
try:
    # centralize config helpers
    from config import load_json, resolve_from_config  # type: ignore
except Exception:
    load_json = None  # will be checked at runtime
    resolve_from_config = None

try:
    from resume_builder import tailor_resume_for_job, build_tailored_resume_doc  # type: ignore
    RESUME_BUILDER_AVAILABLE = True
except Exception:
    RESUME_BUILDER_AVAILABLE = False
try:
    from cover_letter import CoverLetterBuilder  # local module
    COVER_LETTER_AVAILABLE = True
except Exception:
    COVER_LETTER_AVAILABLE = False

try:
    from llm_generate_resume import LLMResumer
    LLM_RESUMER_AVAILABLE = True
except Exception:
    LLM_RESUMER_AVAILABLE = False

try:
    from job_application_generator import JobApplicationGenerator
    JOB_APP_GENERATOR_AVAILABLE = True
except Exception:
    JOB_APP_GENERATOR_AVAILABLE = False

try:
    from llm_cover_letter_adapter import LLMCoverLetterJobDescription
    LLM_COVER_LETTER_AVAILABLE = True
except Exception:
    LLM_COVER_LETTER_AVAILABLE = False

try:
    from llm_parser_adapter import LLMParser
    LLM_PARSER_AVAILABLE = True
except Exception:
    LLM_PARSER_AVAILABLE = False

try:
    from selenium_scraper import (
        fetch_selenium_sites,
        build_selenium_sites_from_company_opts,
        SELENIUM_AVAILABLE
    )
except Exception:
    SELENIUM_AVAILABLE = False
    fetch_selenium_sites = None
    build_selenium_sites_from_company_opts = None

_non_alnum = re.compile(r"[^a-z0-9+#.\-\s]")


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def tokenize_for_fuzz(text: str) -> str:
    text = (text or "").lower()
    text = _non_alnum.sub(" ", text)
    return " ".join(t for t in text.split() if len(t) > 1)


# Basic tech/role keywords to mine from resume text when no explicit query is provided
RESUME_KEYWORDS = [
    "python","java","c++","c#","javascript","typescript","go","rust","sql","nosql",
    "ml","ai","machine","learning","deep","pytorch","tensorflow","keras","sklearn","scikit",
    "data","engineer","scientist","analytics","pipeline","etl","airflow","dbt",
    "aws","azure","gcp","lambda","sagemaker","cloudformation","dynamodb","s3","ec2","kinesis",
    "docker","kubernetes","terraform","jenkins","ansible","gitlab","github","bitbucket",
    "graphql","rest","api","django","flask","fastapi","react","nextjs","node","spark","hadoop"
]


def build_query_from_resume(resume_text: str, max_terms: int = 12) -> str:
    tokens = set(tokenize_for_fuzz(resume_text).split())
    matched = [kw for kw in RESUME_KEYWORDS if kw in tokens]
    if not matched:
        # fallback to a few generic role terms
        matched = [t for t in tokens if len(t) > 3][:max_terms]
    return "|".join(matched[:max_terms])


## cover-letter free text generation now lives in CoverLetterBuilder.compose_concise_text


def _normalize_country_name(country: str | None) -> tuple[str, list[str]]:
    if not country:
        return "", []
    c = country.strip().lower()
    if c in {"usa", "us", "u.s.", "united states", "united states of america"}:
        return "usa", ["united states", "united states of america", "usa", "us", "u.s."]
    return c, [c]


def _matches_country(location_value: str | None, country: str | None) -> bool:
    if not country:
        return True
    if not location_value:
        return True  # keep if unknown
    loc = str(location_value).strip().lower()
    # Always allow fully remote entries
    if "remote" in loc:
        return True
    norm, aliases = _normalize_country_name(country)
    return any(alias in loc for alias in aliases)


def load_jobs(local: str | None, url: str | None, here: Path) -> list[dict[str, Any]]:
    if local:
        with open(local, "r", encoding="utf-8") as f:
            return json.load(f)
    if url:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()
    # No fallback to sample file; return empty list so other sources (e.g., Selenium) can run
    return []


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


FREE_SOURCES = {
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "arbeitnow": fetch_arbeitnow,
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


## resolve_from_config and load_json are provided by config.py


def _arg_present(flag: str) -> bool:
    # Only --config is supported now; keep helper for backward-compat if needed
    return False


def write_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    fields = ["title", "company", "location", "country", "score", "url", "careers_url", "source", "description"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "title": r.get("title", ""),
                "company": r.get("company", ""),
                "location": r.get("location", ""),
                "country": r.get("country", ""),
                "score": r.get("score", ""),
                "url": r.get("url", ""),
                "careers_url": r.get("careers_url", ""),
                "source": r.get("source", ""),
                "description": (r.get("description", "") or "").replace("\r", " ").replace("\n", " ")
            })


def main() -> None:
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Score and list top matching jobs for a given resume (config-only).")
    parser.add_argument("--config", default=None, help="Path to config JSON")
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
    resume_path_candidate = resolved_cfg.get("resume") or None
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

    top_n = int(resolved_cfg.get("top", 10))
    print(resolved_cfg)
    # Source selection
    free_source = resolved_cfg.get("source") if resolved_cfg.get("mode") == "free" else None
    query = resolved_cfg.get("query")
    location = resolved_cfg.get("location")
    country = resolved_cfg.get("country") or "usa"
    serpapi_key = resolved_cfg.get("serpapi_key")
    jobs_arg = resolved_cfg.get("jobs")
    jobs_url_arg = resolved_cfg.get("jobs_url")
    cfg_companies = resolved_cfg.get("companies") or []
    # Combined options from config
    free_opts = resolved_cfg.get("free_options") or {}
    company_opts = resolved_cfg.get("company_options") or {}
    selenium_opts = resolved_cfg.get("selenium_options") or {}
    # Default behavior: run both if neither CLI nor config specifies otherwise
    run_both = bool(resolved_cfg.get("run_both", True))

    # Output handling (configurable dir/prefix)
    out_cfg = resolved_cfg.get("output", {}) if resolved_cfg else {}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = str(here / "output" / f"matched_jobs_{ts}.json")
    if out_cfg:
        out_dir = out_cfg.get("dir")
        prefix = out_cfg.get("prefix", "matched_jobs")
        if out_dir:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = str(Path(here / out_dir / f"{prefix}_{stamp}.json"))

    resume_text = read_text(resume_file)
    # If no explicit query provided, derive it from the resume content
    if not query:
        try:
            query = build_query_from_resume(resume_text)
            print("[query] derived from resume:", query)
        except Exception:
            query = None

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
        # Free block
        free_src = free_source or free_opts.get("source")
        free_query = query or free_opts.get("query")
        if free_src and free_query is not None:
            free_fetcher = FREE_SOURCES.get(free_src)
            if not free_fetcher:
                raise SystemExit(f"Unknown free source: {free_src}")
            fetched += free_fetcher(free_query, int(resolved_cfg.get("fetch_limit", 200)))
        fetched = _dedupe_by_url(fetched)
    else:
        if free_source and query is not None:
            fetcher = FREE_SOURCES.get(free_source)
            if not fetcher:
                raise SystemExit(f"Unknown free source: {free_source}")
            fetched = fetcher(query, int(resolved_cfg.get("fetch_limit", 200)))
        elif serpapi_key and query:
            fetched = fetch_serpapi_google_jobs(query, location, serpapi_key, int(resolved_cfg.get("fetch_limit", 200)))
        else:
            fetched = load_jobs(jobs_arg, jobs_url_arg, here)
            if isinstance(fetched, dict) and 'items' in fetched:
                fetched = fetched['items']  # normalize
            if not isinstance(fetched, list):
                fetched = []
            fetched = fetched[: int(resolved_cfg.get("fetch_limit", 200))]

    # Optional Selenium fetch
    use_selenium = bool(selenium_opts.get("enabled"))
    print(use_selenium)
    if use_selenium:
        # Prefer explicit sites; otherwise derive from company_options
        raw_sites = selenium_opts.get("sites") or build_selenium_sites_from_company_opts(cfg_companies)
        try:
            def _u(x):
                return x.get("url") if isinstance(x, dict) else str(x)
            print("[selenium] using sites:", [_u(s) for s in (raw_sites or [])])
        except Exception:
            pass
        if raw_sites:
            fetched += fetch_selenium_sites(raw_sites, int(resolved_cfg.get("fetch_limit", 200)))

    # Country filter (lenient, allows 'Remote')
    if country:
        fetched = [j for j in fetched if _matches_country(j.get("location"), country)]

    # Score and select
    scored = []
    for job in fetched:
        s = score_job(job, resume_text)
        # derive country value for CSV
        cval = "usa" if _matches_country(job.get("location"), "usa") else ""
        scored.append({**job, "score": round(s, 2), "country": cval})
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: top_n]

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(top, f, indent=2)

    # CSV path for top N
    csv_path = out_file.with_suffix('.csv')
    write_csv(top, csv_path)

    # Save fetched list (JSON/CSV) if requested
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fetched_json = out_file.parent / f"fetched_jobs_{stamp}.json"
    fetched_csv = out_file.parent / f"fetched_jobs_{stamp}.csv"
    if (resolved_cfg.get("save_fetched") or False):
        with open(fetched_json, "w", encoding="utf-8") as f:
            json.dump(fetched, f, indent=2)
        # add dummy score column for CSV uniformity
        fetched_rows = [{**j, "score": "", "country": ("usa" if _matches_country(j.get("location"), "usa") else "")} for j in fetched]
        write_csv(fetched_rows, fetched_csv)

    # Always also produce top-50 alongside configured top
    top50 = scored[:50]
    top50_json = out_file.parent / f"top50_jobs_{stamp}.json"
    top50_csv = out_file.parent / f"top50_jobs_{stamp}.csv"
    with open(top50_json, "w", encoding="utf-8") as f:
        json.dump(top50, f, indent=2)
    write_csv(top50, top50_csv)

    # Generate cover letters for top 100 (concise, three-paragraph letters; no greeting/signature)
    if (COVER_LETTER_AVAILABLE or LLM_RESUMER_AVAILABLE or JOB_APP_GENERATOR_AVAILABLE) and top:
        try:
            letters_dir = out_file.parent / "cover_letters"
            letters_dir.mkdir(parents=True, exist_ok=True)
            # Derive candidate name from resume first non-empty line
            name_line = next((ln.strip() for ln in resume_text.splitlines() if ln.strip()), "Candidate")
            openai_cfg = resolved_cfg.get("openai") or {}
            use_openai = bool(openai_cfg.get("enabled"))
            openai_model = (openai_cfg.get("model") or "").strip()
            openai_key = (openai_cfg.get("api_key") or os.getenv("OPENAI_API_KEY") or "").strip()
            
            # Initialize JobApplicationGenerator (preferred method)
            use_job_app_gen = bool(resolved_cfg.get("use_job_app_generator", True)) and JOB_APP_GENERATOR_AVAILABLE and use_openai and openai_key
            job_app_gen = None
            if use_job_app_gen:
                try:
                    job_app_gen = JobApplicationGenerator(openai_key)
                    job_app_gen.set_resume(resume_text)
                    print("[jobgen] Using JobApplicationGenerator (unified LangChain pipeline)")
                except Exception as e:
                    print(f"[jobgen] Failed to initialize JobApplicationGenerator: {e}. Falling back.")
                    use_job_app_gen = False
            
            # Fallback: Initialize LLMCoverLetterJobDescription for cover letters  
            use_llm_resumer = False
            llm_resumer = None
            llm_resumer_ready = False
            use_llm_cover = False
            llm_cover = None

            if LLM_RESUMER_AVAILABLE and use_openai and openai_key:
                try:
                    llm_resumer = LLMResumer(openai_key)
                    llm_resumer.set_resume_data(resume_text)
                    llm_resumer_ready = True
                    use_llm_resumer = True
                    print("[llm] LLMResumer initialized and will be used for resume generation")
                except Exception as e:
                    llm_resumer = None
                    llm_resumer_ready = False
                    print(f"[llm] Failed to initialize LLMResumer: {e}. Falling back.")
            
            if not use_job_app_gen and not use_llm_resumer and LLM_COVER_LETTER_AVAILABLE and use_openai and openai_key:
                try:
                    llm_cover = LLMCoverLetterJobDescription(openai_key)
                    llm_cover.set_resume(resume_text)
                    use_llm_cover = True
                    print("[llmcover] Using LLMCoverLetterJobDescription (LangChain) for cover letter generation")
                except Exception as e:
                    print(f"[llmcover] Failed to initialize LLMCoverLetterJobDescription: {e}. Falling back.")
            
            # Initialize LLMParser for job description enrichment
            use_llm_parser = False
            llm_parser = None
            if LLM_PARSER_AVAILABLE and use_openai and openai_key:
                try:
                    llm_parser = LLMParser(openai_key)
                    use_llm_parser = True
                    print("[parser] Using LLMParser (RAG-based) for job description parsing")
                except Exception as e:
                    print(f"[parser] Failed to initialize LLMParser: {e}. Skipping enhanced parsing.")
            
            # Final fallback to CoverLetterBuilder
            builder = None
            if not use_job_app_gen and not use_llm_resumer and not use_llm_cover and COVER_LETTER_AVAILABLE:
                builder = CoverLetterBuilder(resume_text, name_line)
            
            # Auto-tailor resume and generate cover letter for jobs with score > 40
            auto_tailor = bool(resolved_cfg.get("auto_tailor_resume", False))
            tailor_threshold = int(resolved_cfg.get("tailor_threshold", 40))
            enforced_tailor_threshold = max(tailor_threshold, 40)
            tailored_resumes_dir = out_file.parent / "tailored_resumes"
            if auto_tailor:
                tailored_resumes_dir.mkdir(parents=True, exist_ok=True)
            
            for idx, j in enumerate(top[:100]):
                score = j.get("score", 0)
                company = (j.get("company") or "").strip() or "Company"
                role = (j.get("title") or "").strip() or "Role"
                jd_text = (j.get("description") or "").strip()
                base = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{company}_{role}")[:80]
                llm_resume_generated = False
                llm_resume_text = None
                builder_tailored = builder
                should_force_llm_resume = False
                
                # Debug: log job details
                print(f"[cover] {idx+1}/100: {company} - {role} | Score: {score} | JD length: {len(jd_text)} chars")
                if len(jd_text) < 50:
                    print(f"  WARNING: Job description too short or empty for {company}")
                
                # Use LLMParser to enrich job information if available
                parsed_info = None
                if use_llm_parser and jd_text:
                    try:
                        print(f"  [parser] Parsing job description for {company}...")
                        parsed_info = llm_parser.parse_job_from_text(jd_text)
                        
                        # Update job fields with parsed information if better
                        if parsed_info.get("company") and parsed_info["company"] != "Not specified":
                            company = parsed_info["company"]
                        if parsed_info.get("role") and parsed_info["role"] != "Not specified":
                            role = parsed_info["role"]
                        
                        # Save parsed info
                        if parsed_info:
                            parsed_dir = out_file.parent / "parsed_jobs"
                            parsed_dir.mkdir(parents=True, exist_ok=True)
                            parsed_path = parsed_dir / f"parsed_{base}.txt"
                            with open(parsed_path, "w", encoding="utf-8") as f:
                                f.write(f"Company: {parsed_info.get('company', 'N/A')}\n")
                                f.write(f"Role: {parsed_info.get('role', 'N/A')}\n")
                                f.write(f"Location: {parsed_info.get('location', 'N/A')}\n")
                                f.write(f"Salary: {parsed_info.get('salary_range', 'N/A')}\n")
                                f.write(f"Email: {parsed_info.get('recruiter_email', 'N/A')}\n\n")
                                f.write(f"Required Skills:\n{parsed_info.get('required_skills', 'N/A')}\n\n")
                                f.write(f"Preferred Skills:\n{parsed_info.get('preferred_skills', 'N/A')}\n\n")
                                f.write(f"Description:\n{parsed_info.get('description', 'N/A')}\n")
                    except Exception as e:
                        print(f"  [parser] Error parsing {company}: {e}")
                        parsed_info = None
                
                job_summary_override = ""
                job_description_override = jd_text
                job_keywords_override = ""
                if parsed_info:
                    job_summary_override = (parsed_info.get("description") or "").strip()
                    if job_summary_override:
                        job_description_override = job_summary_override
                    skill_terms: list[str] = []
                    for key in ("required_skills", "preferred_skills"):
                        field_val = (parsed_info.get(key) or "").strip()
                        if field_val:
                            skill_terms.extend(
                                kw.strip()
                                for kw in re.split(r"[,\n;]", field_val)
                                if kw.strip()
                            )
                    if skill_terms:
                        seen_terms: list[str] = []
                        for kw in skill_terms:
                            if kw not in seen_terms:
                                seen_terms.append(kw)
                        job_keywords_override = ", ".join(seen_terms)
                job_context_llm = {
                    "job_summary": job_summary_override or job_description_override,
                    "job_description": job_description_override,
                    "job_keywords": job_keywords_override,
                    "company": company,
                    "role": role,
                }
                should_force_llm_resume = llm_resumer_ready and auto_tailor and bool(jd_text)
                llm_cover_generated = False
                
                def write_llm_cover_letter() -> None:
                    nonlocal llm_cover_generated, builder_tailored
                    if llm_cover_generated:
                        return
                    if not (llm_resumer_ready and auto_tailor and jd_text):
                        return
                    try:
                        cover_letter_llm = llm_resumer.generate_cover_letter(
                            jd_text, company, role, job_context=job_context_llm
                        ) if llm_resumer else None
                        if cover_letter_llm:
                            txt_path = letters_dir / f"cover_{base}.txt"
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(cover_letter_llm)
                            llm_cover_generated = True
                            builder_tailored = None
                            print(f"  [llm] Cover letter saved for {company} using LLMResumer")
                    except Exception as e:
                        print(f"  [llm] Cover letter generation failed for {company}: {e}")
                
                # Method 1: JobApplicationGenerator (unified, preferred)
                jobgen_success = False
                if use_job_app_gen and auto_tailor and jd_text:
                    try:
                        print(f"  [jobgen] Generating application package for {company}...")
                        result = job_app_gen.generate_application_package(jd_text, company, role, parallel=True)
                        
                        # Save tailored resume
                        if result.get("resume"):
                            resume_path = tailored_resumes_dir / f"resume_{base}.txt"
                            with open(resume_path, "w", encoding="utf-8") as f:
                                f.write(result["resume"])
                        
                        # Save cover letter
                        if result.get("cover_letter"):
                            txt_path = letters_dir / f"cover_{base}.txt"
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(result["cover_letter"])
                        
                        # Optionally save job summary
                        if result.get("job_summary"):
                            summary_dir = out_file.parent / "job_summaries"
                            summary_dir.mkdir(parents=True, exist_ok=True)
                            summary_path = summary_dir / f"summary_{base}.txt"
                            with open(summary_path, "w", encoding="utf-8") as f:
                                f.write(result["job_summary"])
                        
                        jobgen_success = True
                    except Exception as e:
                        print(f"  [jobgen] Error for {company}: {e}. Falling back.")
                
                if jobgen_success:
                    if should_force_llm_resume and not llm_resume_generated:
                        try:
                            llm_resume_text = (
                                llm_resumer.generate_tailored_resume(
                                    jd_text, company, role, job_context=job_context_llm
                                )
                                if llm_resumer
                                else None
                            )
                            if llm_resume_text:
                                resume_path = tailored_resumes_dir / f"resume_{base}.txt"
                                with open(resume_path, "w", encoding="utf-8") as f:
                                    f.write(llm_resume_text)
                                llm_resume_generated = True
                                print(f"  [llm] Tailored resume saved for {company} using LLMResumer")
                        except Exception as e:
                            print(f"  [llm] Tailored resume generation failed for {company}: {e}")
                    write_llm_cover_letter()
                    continue  # Skip to next job
                
                # Method 2: LLMResumer (parallel resume + cover letter generation)
                if use_llm_resumer and auto_tailor and jd_text:
                    try:
                        print(f"  [llm] Generating resume + cover letter for {company} using LangChain...")
                        resume_text_llm = llm_resumer.generate_tailored_resume(
                            jd_text, company, role, job_context=job_context_llm
                        )
                        cover_letter_llm = llm_resumer.generate_cover_letter(
                            jd_text, company, role, job_context=job_context_llm
                        )
                        
                        if resume_text_llm:
                            resume_path = tailored_resumes_dir / f"resume_{base}.txt"
                            with open(resume_path, "w", encoding="utf-8") as f:
                                f.write(resume_text_llm)
                            llm_resume_text = resume_text_llm
                            llm_resume_generated = True
                        
                        if cover_letter_llm:
                            txt_path = letters_dir / f"cover_{base}.txt"
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(cover_letter_llm)
                            llm_cover_generated = True
                            builder_tailored = None
                        
                        continue  # Skip to next job
                    except Exception as e:
                        print(f"  [llm] Error for {company}: {e}. Falling back to standard method.")
                
                # Fallback: Standard resume tailoring (if score > threshold)
                builder_tailored = builder
                if auto_tailor and RESUME_BUILDER_AVAILABLE and score >= enforced_tailor_threshold and jd_text:
                    try:
                        tailored_text = tailor_resume_for_job(
                            resume_text, jd_text, company, role, openai_model, openai_key
                        )
                        if tailored_text and tailored_text != resume_text:
                            tailored_doc = build_tailored_resume_doc(tailored_text)
                            resume_path = tailored_resumes_dir / f"resume_{base}.docx"
                            tailored_doc.save(resume_path)
                            if should_force_llm_resume and not llm_resume_generated:
                                try:
                                    llm_resume_text = (
                                        llm_resumer.generate_tailored_resume(
                                            jd_text, company, role, job_context=job_context_llm
                                        )
                                        if llm_resumer
                                        else None
                                    )
                                    if llm_resume_text:
                                        resume_txt_path = tailored_resumes_dir / f"resume_{base}.txt"
                                        with open(resume_txt_path, "w", encoding="utf-8") as f:
                                            f.write(llm_resume_text)
                                        llm_resume_generated = True
                                        print(f"  [llm] Tailored resume saved for {company} using LLMResumer")
                                except Exception as e:
                                    print(f"  [llm] Tailored resume generation failed for {company}: {e}")
                            if COVER_LETTER_AVAILABLE:
                                if llm_resume_generated and llm_resume_text:
                                    builder_tailored = CoverLetterBuilder(llm_resume_text, name_line)
                                else:
                                    builder_tailored = CoverLetterBuilder(tailored_text, name_line)
                    except Exception as e:
                        print(f"[resume_tailor] error for {company}: {e}")
                
                if should_force_llm_resume and not llm_resume_generated:
                    try:
                        llm_resume_text = (
                            llm_resumer.generate_tailored_resume(
                                jd_text, company, role, job_context=job_context_llm
                            )
                            if llm_resumer
                            else None
                        )
                        if llm_resume_text:
                            resume_txt_path = tailored_resumes_dir / f"resume_{base}.txt"
                            with open(resume_txt_path, "w", encoding="utf-8") as f:
                                f.write(llm_resume_text)
                            llm_resume_generated = True
                            print(f"  [llm] Tailored resume saved for {company} using LLMResumer")
                            if COVER_LETTER_AVAILABLE:
                                builder_tailored = CoverLetterBuilder(llm_resume_text, name_line)
                    except Exception as e:
                        print(f"  [llm] Tailored resume generation failed for {company}: {e}")
                
                write_llm_cover_letter()
                
                # Method 3: LLMCoverLetterJobDescription (cover letter only)
                if not llm_cover_generated and use_llm_cover and jd_text:
                    try:
                        print(f"  [llmcover] Generating cover letter for {company} using LangChain...")
                        resume_for_letter = llm_resume_text if llm_resume_text else resume_text
                        letter_txt = llm_cover.generate_from_job_and_resume(jd_text, resume_for_letter)
                        if letter_txt:
                            txt_path = letters_dir / f"cover_{base}.txt"
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(letter_txt)
                            continue  # Skip to next job
                    except Exception as e:
                        print(f"  [llmcover] Error for {company}: {e}. Falling back.")
                
                # Compose cover letter using standard method
                if not llm_cover_generated:
                    letter_txt = None
                    if builder_tailored and use_openai and openai_key:
                        letter_txt = builder_tailored.compose_openai_text(jd_text, company, role, openai_model, openai_key)
                    if not letter_txt and builder_tailored:
                        letter_txt = builder_tailored.compose_concise_text(jd_text, company, role)
                
                    if letter_txt:
                        txt_path = letters_dir / f"cover_{base}.txt"
                        with open(txt_path, "w", encoding="utf-8") as f:
                            f.write(letter_txt)
            
            print(f"[cover] generated cover letters in {letters_dir}")
            if auto_tailor:
                print(f"[resume] generated tailored resumes in {tailored_resumes_dir}")
        except Exception as e:
            print("[cover] skipped:", e)
    print("Top matches:")
    for j in top:
        line = f"- [{j['score']}] {j.get('title','')} @ {j.get('company','')} ({j.get('location','')})"
        if j.get("url"):
            line += f" - {j['url']}"
        print(line)
    print("Saved to:", os.path.abspath(out_file))
    print("CSV saved to:", os.path.abspath(csv_path))
    if resolved_cfg.get("save_fetched"):
        print("Fetched JSON:", os.path.abspath(fetched_json))
        print("Fetched CSV:", os.path.abspath(fetched_csv))
    print("Top50 JSON:", os.path.abspath(top50_json))
    print("Top50 CSV:", os.path.abspath(top50_csv))


if __name__ == "__main__":
    main()
