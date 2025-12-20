import argparse
import json
import os
import re
import sys
import csv
from datetime import datetime
from urllib.parse import urljoin, urlparse
from pathlib import Path
from typing import Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    import openai_compat  # noqa: F401
except Exception:
    openai_compat = None

if load_dotenv:
    load_dotenv()

import requests
try:
    # Prefer rapidfuzz if available (much faster + better token-set scoring).
    from rapidfuzz import fuzz  # type: ignore
except Exception:
    # Pure-Python fallback so the script can run without pip installs.
    # We emulate fuzz.token_set_ratio using normalized token overlap + SequenceMatcher.
    import difflib

    class _FuzzFallback:
        @staticmethod
        def token_set_ratio(a: str, b: str) -> float:
            def _tok(s: str) -> set[str]:
                return {t for t in (s or "").lower().split() if t}

            a_set = _tok(a)
            b_set = _tok(b)
            if not a_set and not b_set:
                return 100.0
            if not a_set or not b_set:
                return 0.0

            inter = sorted(a_set & b_set)
            a_only = sorted(a_set - b_set)
            b_only = sorted(b_set - a_set)

            # Similar to the canonical approach: compare intersections and unions as strings.
            s1 = " ".join(inter)
            s2 = " ".join(inter + a_only)
            s3 = " ".join(inter + b_only)

            def _ratio(x: str, y: str) -> float:
                return difflib.SequenceMatcher(None, x, y).ratio() * 100.0

            return max(_ratio(s1, s2), _ratio(s1, s3), _ratio(s2, s3))

    fuzz = _FuzzFallback()
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
    from llm_job_description_extractor import JobDescriptionExtractor
    JOB_DESC_EXTRACTOR_AVAILABLE = True
except Exception:
    JOB_DESC_EXTRACTOR_AVAILABLE = False
try:
    from llm_job_parser import LLMParser as LLMJobHTMLParser
    LLM_JOB_HTML_PARSER_AVAILABLE = True
except Exception:
    LLM_JOB_HTML_PARSER_AVAILABLE = False
    LLMJobHTMLParser = None

try:
    from llm_selenium_site_builder import generate_selenium_site_entries  # type: ignore
    LLM_SELENIUM_SITE_BUILDER_AVAILABLE = True
except Exception:
    LLM_SELENIUM_SITE_BUILDER_AVAILABLE = False
    generate_selenium_site_entries = None  # type: ignore

try:
    from selenium_scraper import (
        fetch_selenium_sites,
        SELENIUM_AVAILABLE,
        create_chrome_driver,
    )
except Exception:
    SELENIUM_AVAILABLE = False
    fetch_selenium_sites = None
    create_chrome_driver = None

try:
    from workday_autofill import (
        CandidateProfile as WorkdayCandidateProfile,
        WorkdayAutofill,
        is_workday_url,
    )
    WORKDAY_AUTOFILL_AVAILABLE = True
except Exception:
    WORKDAY_AUTOFILL_AVAILABLE = False
    WorkdayCandidateProfile = None  # type: ignore
    WorkdayAutofill = None  # type: ignore
    is_workday_url = lambda _: False  # type: ignore

try:
    from portal_autofill import (
        CandidateProfile as PortalCandidateProfile,
        SimpleGreenhouseAutofill,
        SimpleLeverAutofill,
        is_greenhouse_url,
        is_lever_url,
    )
    PORTAL_AUTOFILL_AVAILABLE = True
except Exception:
    PORTAL_AUTOFILL_AVAILABLE = False
    PortalCandidateProfile = None  # type: ignore
    SimpleGreenhouseAutofill = None  # type: ignore
    SimpleLeverAutofill = None  # type: ignore
    is_greenhouse_url = lambda _: False  # type: ignore
    is_lever_url = lambda _: False  # type: ignore
from resume_utils import load_resume_data

_non_alnum = re.compile(r"[^a-z0-9+#.\-\s]")
_html_strip_re = re.compile(r"<[^>]+>")
_html_script_style_re = re.compile(r"(?is)<(script|style).*?>.*?</\\1>")

def _normalize_meta_field(value: str | None) -> str:
    """Normalize company/role/location fields, stripping placeholder text."""
    if not value:
        return ""
    cleaned = value.strip()
    lowered = cleaned.lower()
    if lowered in {"not specified", "not specified."}:
        return ""
    return cleaned


def tokenize_for_fuzz(text: str) -> str:
    text = (text or "").lower()
    text = _non_alnum.sub(" ", text)
    return " ".join(t for t in text.split() if len(t) > 1)


# Domain keywords to mine from resume text when no explicit query is provided.
# For this project we focus on AUTOMOTIVE / SAFETY / SYSTEMS roles (not generic coding).
RESUME_KEYWORDS = [
    # Core domain
    "automotive", "vehicle", "ev", "electric", "hybrid", "powertrain", "chassis",
    "braking", "steering", "ecu", "can", "lin", "flexray", "ethernet", "autosar",
    "embedded", "controller", "sensor", "actuator",
    # ADAS / autonomous
    "adas", "autonomous", "self-driving", "selfdriving", "autonomy",
    "perception", "sensorfusion", "sensor-fusion", "lane", "adaptive", "cruise",
    # Safety / systems engineering
    "functional", "safety", "functional-safety", "system-safety", "systems",
    "systems-engineering", "systems engineer", "system engineer",
    "iso26262", "iso 26262", "asil", "hara", "fmea", "dfmea", "pfmea", "fta",
    "safety-case", "safety case", "sotif", "iec61508", "arp4754",
    # Requirements / MBSE / tools
    "requirements", "requirement", "doors", "polarion", "jama",
    "sysml", "uml", "mbse", "v-model", "verification", "validation", "integration", "test",
    "hil", "hardware-in-the-loop", "sil", "mil",
]


def build_query_from_resume(resume_text: str, max_terms: int = 12) -> str:
    """
    Automatically derive a search query from the resume text, without requiring
    a hard-coded keyword list.
    
    Strategy:
      - tokenize the resume
      - count word and 2-word phrase frequencies
      - drop very common stopwords and very short tokens
      - take the top-N most frequent phrases/words
    """
    from collections import Counter

    tokens = tokenize_for_fuzz(resume_text).split()
    if not tokens:
        return ""

    # Very small stopword list; this keeps implementation simple and domain-agnostic
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "have", "will",
        "your", "their", "they", "them", "into", "over", "under", "above",
        "below", "more", "less", "than", "such", "including", "across",
        "within", "between", "other", "role", "responsible", "experience",
        "years", "year", "work", "working", "team", "teams",
    }

    filtered = [t for t in tokens if len(t) > 3 and t not in stopwords]
    if not filtered:
        return ""

    # 1-gram frequencies
    uni_counter = Counter(filtered)

    # 2-gram (bigram) frequencies, built from adjacent tokens
    bigrams: list[str] = []
    for i in range(len(filtered) - 1):
        w1, w2 = filtered[i], filtered[i + 1]
        if w1 in stopwords or w2 in stopwords:
            continue
        phrase = f"{w1} {w2}"
        bigrams.append(phrase)
    bi_counter = Counter(bigrams)

    # Build final list preferring bigrams, then unigrams
    terms: list[str] = []

    for phrase, _ in bi_counter.most_common(max_terms):
        if phrase not in terms:
            terms.append(phrase)
        if len(terms) >= max_terms:
            break

    if len(terms) < max_terms:
        for word, _ in uni_counter.most_common(max_terms):
            if word not in terms:
                terms.append(word)
            if len(terms) >= max_terms:
                break

    return "|".join(terms[:max_terms])


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


def load_selenium_sites_from_opts(opts: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Selenium site definitions from config."""
    sites: list[dict[str, Any]] = []
    if not opts:
        return sites

    seen_keys: set[str] = set()

    def _add_sites(items: Any) -> None:
        if not items:
            return
        if isinstance(items, dict):
            _add_sites(items.get("sites"))
            return
        if not isinstance(items, list):
            return
        for entry in items:
            if not isinstance(entry, dict):
                continue
            company = (entry.get("company") or "").strip().lower()
            url = (entry.get("url") or "").strip().lower()
            key = company or url
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            sites.append(entry)

    _add_sites(opts.get("sites"))
    _add_sites(opts.get("extra_sites"))

    opts["sites"] = sites
    return sites


def _slugify_company_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _normalize_company_entries(entries: Any) -> List[Tuple[str, str]]:
    normalized: List[Tuple[str, str]] = []
    if not entries:
        return normalized
    if not isinstance(entries, list):
        entries = [entries]
    for entry in entries:
        if isinstance(entry, dict):
            raw_name = str(entry.get("name") or entry.get("company") or entry.get("slug") or "").strip()
            slug = str(entry.get("slug") or "").strip()
            if not slug and raw_name:
                slug = _slugify_company_name(raw_name)
        else:
            raw_name = str(entry or "").strip()
            slug = _slugify_company_name(raw_name)
        if not slug:
            continue
        normalized.append((raw_name or slug, slug))
    return normalized


def generate_company_source_sites(company_sources_cfg: dict[str, Any]) -> Tuple[List[dict[str, Any]], List[str]]:
    """
    Generate Selenium site entries for known hosted job boards (Lever, Greenhouse).
    """
    generated_sites: List[dict[str, Any]] = []
    generated_companies: List[str] = []
    seen_slugs: set[str] = set()

    if not company_sources_cfg:
        return generated_sites, generated_companies

    lever_cfg = company_sources_cfg.get("lever") or {}
    if lever_cfg.get("enabled"):
        defaults = {
            "list_selector": lever_cfg.get("list_selector") or "div.posting, div[data-qa='posting'], ul.postings-list li",
            "title_selector": lever_cfg.get("title_selector") or "a[data-qa='posting-name'], a.posting-title, h5.posting-title",
            "location_selector": lever_cfg.get("location_selector") or "span.posting-location, div.posting-location",
            "link_selector": lever_cfg.get("link_selector") or "a[data-qa='posting-name'], a.posting-title",
            "wait_selector": lever_cfg.get("wait_selector") or "a[data-qa='posting-name'], a.posting-title",
        }
        for _, slug in _normalize_company_entries(lever_cfg.get("companies")):
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            site = {
                "company": slug,
                "url": f"https://jobs.lever.co/{slug}",
                "careers_url": f"https://jobs.lever.co/{slug}",
                "list_selector": defaults["list_selector"],
                "title_selector": defaults["title_selector"],
                "location_selector": defaults["location_selector"],
                "link_selector": defaults["link_selector"],
                "wait_selector": defaults["wait_selector"],
                "source": f"selenium:lever:{slug}",
                "domain_filter": "lever.co",
                "absolute_base": "https://jobs.lever.co",
                "sleep_seconds": lever_cfg.get("sleep_seconds", 3),
            }
            generated_sites.append(site)
            generated_companies.append(slug)

    greenhouse_cfg = company_sources_cfg.get("greenhouse") or {}
    if greenhouse_cfg.get("enabled"):
        defaults = {
            "list_selector": greenhouse_cfg.get("list_selector") or "section.opening, div.opening, ul.openings li",
            "title_selector": greenhouse_cfg.get("title_selector") or "a[href*='boards.greenhouse.io'], h3",
            "location_selector": greenhouse_cfg.get("location_selector") or "span.location, div.location",
            "link_selector": greenhouse_cfg.get("link_selector") or "a[href*='boards.greenhouse.io']",
            "wait_selector": greenhouse_cfg.get("wait_selector") or "a[href*='boards.greenhouse.io']",
        }
        for _, slug in _normalize_company_entries(greenhouse_cfg.get("companies")):
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            site = {
                "company": slug,
                "url": f"https://boards.greenhouse.io/{slug}",
                "careers_url": f"https://boards.greenhouse.io/{slug}",
                "list_selector": defaults["list_selector"],
                "title_selector": defaults["title_selector"],
                "location_selector": defaults["location_selector"],
                "link_selector": defaults["link_selector"],
                "wait_selector": defaults["wait_selector"],
                "source": f"selenium:greenhouse:{slug}",
                "domain_filter": "greenhouse.io",
                "absolute_base": "https://boards.greenhouse.io",
                "sleep_seconds": greenhouse_cfg.get("sleep_seconds", 3),
            }
            generated_sites.append(site)
            generated_companies.append(slug)

    return generated_sites, generated_companies


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    # Simple HTML tag removal
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_lever_jobs(slug: str, display_name: str, fetch_limit: int) -> List[dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        postings = resp.json()
        if not isinstance(postings, list):
            return []
    except Exception as exc:
        print(f"[lever] Failed to fetch postings for {slug}: {exc}")
        return []

    jobs: List[dict[str, Any]] = []
    for post in postings[:fetch_limit]:
        if not isinstance(post, dict):
            continue
        title = post.get("text") or post.get("title")
        job_url = (
            post.get("hostedUrl")
            or post.get("applyUrl")
            or post.get("applyUrl")
        )
        if not title or not job_url:
            continue
        categories = post.get("categories") or {}
        location = categories.get("location") or categories.get("commitment") or ""
        desc_plain = post.get("descriptionPlain")
        desc_html = post.get("description")
        description = desc_plain or _html_to_text(desc_html or "")

        jobs.append({
            "title": title.strip(),
            "company": display_name,
            "location": location.strip(),
            "url": job_url.strip(),
            "description": description,
            "source": f"lever:{slug}",
        })
    print(f"[lever] Retrieved {len(jobs)} jobs for {slug}")
    return jobs


def _fetch_greenhouse_jobs(slug: str, display_name: str, fetch_limit: int, country_filter: str | None = None) -> List[dict[str, Any]]:
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        resp = requests.get(api_url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        jobs_payload = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs_payload, list):
            return []
    except Exception as exc:
        print(f"[greenhouse] Failed to fetch jobs for {slug}: {exc}")
        return []

    jobs: List[dict[str, Any]] = []
    # Prepare country aliases for simple filtering
    norm_country = (country_filter or "").strip().lower()
    aliases: list[str] = []
    if norm_country:
        if norm_country in {"usa", "us", "u.s.", "united states", "united states of america"}:
            aliases = ["usa", "us", "u.s.", "united states", "united states of america"]
        elif norm_country in {"uk", "u.k.", "united kingdom"}:
            aliases = ["uk", "u.k.", "united kingdom", "england", "scotland", "wales", "northern ireland"]
        elif norm_country in {"uae", "united arab emirates"}:
            aliases = ["uae", "united arab emirates"]
        elif norm_country in {"germany", "deutschland"}:
            aliases = ["germany", "deutschland"]
        else:
            aliases = [norm_country]

    for job in jobs_payload[:fetch_limit]:
        if not isinstance(job, dict):
            continue
        job_id = job.get("id")
        title = job.get("title")
        absolute_url = job.get("absolute_url")
        if not job_id or not title or not absolute_url:
            continue
        location = ""
        if isinstance(job.get("location"), dict):
            location = job["location"].get("name", "")

        # Country filter: include only if location matches desired country aliases
        if aliases:
            loc_lower = (location or "").strip().lower()
            if not any(alias in loc_lower for alias in aliases):
                # Skip non-matching locations
                continue

        description_text = ""
        detail_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"
        try:
            detail_resp = requests.get(detail_url, timeout=30)
            detail_resp.raise_for_status()
            detail_payload = detail_resp.json()
            if isinstance(detail_payload, dict):
                description_text = _html_to_text(detail_payload.get("content", ""))
        except Exception as exc:
            print(f"[greenhouse] Failed to fetch detail for {slug}/{job_id}: {exc}")

        jobs.append({
            "title": title.strip(),
            "company": display_name,
            "location": location.strip(),
            "url": absolute_url.strip(),
            "description": description_text,
            "source": f"greenhouse:{slug}",
        })
    print(f"[greenhouse] Retrieved {len(jobs)} jobs for {slug}")
    return jobs


def fetch_company_source_jobs(company_sources_cfg: dict[str, Any], fetch_limit: int, country_filter: str | None = None) -> List[dict[str, Any]]:
    jobs: List[dict[str, Any]] = []
    if not company_sources_cfg:
        return jobs

    lever_cfg = company_sources_cfg.get("lever") or {}
    if lever_cfg.get("enabled"):
        entries = _normalize_company_entries(lever_cfg.get("companies"))
        per_company_limit = max(1, fetch_limit // max(1, len(entries))) if entries else fetch_limit
        for raw_name, slug in entries:
            display = raw_name or slug
            jobs.extend(_fetch_lever_jobs(slug, display, per_company_limit))

    greenhouse_cfg = company_sources_cfg.get("greenhouse") or {}
    if greenhouse_cfg.get("enabled"):
        entries = _normalize_company_entries(greenhouse_cfg.get("companies"))
        per_company_limit = max(1, fetch_limit // max(1, len(entries))) if entries else fetch_limit
        # Allow per-provider override: company_sources.greenhouse.country
        gh_country = (greenhouse_cfg.get("country") or country_filter)
        for raw_name, slug in entries:
            display = raw_name or slug
            jobs.extend(_fetch_greenhouse_jobs(slug, display, per_company_limit, gh_country))

    return jobs


def fetch_serpapi_google_jobs(query: str, location: str | None, api_key: str, fetch_limit: int) -> list[dict[str, Any]]:
    params = {
        "engine": "google_jobs",
        "q": query,
        "hl": "en",
        "api_key": api_key,
    }
    if location:
        params["location"] = location
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=60)  # Increased from 30 to 60
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


def fetch_job_description_plain(url: str, max_chars: int = 12000) -> str:
    """Fetch job description from URL, stripping HTML tags. Increased timeout."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            )
        }
        resp = requests.get(url, timeout=60, headers=headers)  # Increased from 20 to 60
        resp.raise_for_status()
        html_text = resp.text
    except Exception:
        return ""
    cleaned = _html_script_style_re.sub(" ", html_text)
    cleaned = _html_strip_re.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    return cleaned[:max_chars]


def fetch_job_description_with_playwright(url: str, max_chars: int = 12000) -> str:
    """
    Fetch job description using Playwright for JavaScript rendering.
    This handles dynamic content like Meta careers pages.
    """
    try:
        import asyncio
        from playwright.async_api import async_playwright  # noqa: F401
        
        async def get_description():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=60000, wait_until="networkidle")
                
                # Wait a bit more for any lazy-loaded content
                await page.wait_for_timeout(2000)
                
                html = await page.content()
                await browser.close()
                return html
        
        # Get event loop and run async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        html_text = loop.run_until_complete(get_description())
        
        # Strip HTML tags
        cleaned = _html_script_style_re.sub(" ", html_text)
        cleaned = _html_strip_re.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        if not cleaned or len(cleaned) < 50:
            return ""
        
        return cleaned[:max_chars]
    
    except ImportError:
        # Playwright not installed - silently skip
        return ""
    except Exception as e:
        # On any error, silently return empty (browsers may not be installed in CI/CD)
        error_msg = str(e)
        if "Executable doesn't exist" in error_msg or "ms-playwright" in error_msg:
            # Browser not installed - this is expected in some environments, don't print error
            pass
        else:
            # Other errors - print for debugging
            print(f"  [playwright] Error: {type(e).__name__}: {str(e)[:100]}")
        return ""


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


# Free-source fetching removed by request.


def check_sponsorship_available(jd_text: str, check_enabled: bool = False) -> bool:
    """
    Check if job description indicates visa/sponsorship is NOT available.
    Returns True if sponsorship appears to be available, False if explicitly not available.
    
    Args:
        jd_text: Job description text
        check_enabled: Enable sponsorship check (disabled by default to avoid over-filtering)
    
    Returns:
        bool: True if sponsorship available, False if explicitly blocked
    """
    if not check_enabled:
        return True  # Always pass if check is disabled
    
    if not jd_text:
        return True  # Assume sponsorship available if no text
    
    jd_lower = jd_text.lower()
    
    # Patterns indicating NO sponsorship
    no_sponsorship_patterns = [
        r"visa\s+sponsorship\s+is\s+not\s+available",
        r"(?:no|not)\s+(?:visa|work\s+permit)\s+sponsorship",
        r"sponsorship\s+(?:is\s+)?not\s+(?:available|provided)",
        r"(?:visa|sponsorship|work\s+permit)\s+(?:is\s+)?not\s+available",
        r"requires?.+?(?:us\s+(?:citizen|passport)|green\s+card|permanent\s+resident)",
        r"(?:us\s+)?(?:citizen|citizenship|gc|green\s+card|permanent\s+resident)",
        r"no\s+(?:visa|sponsorship|work\s+permit)\s+(?:available|provided)",
        r"(?:only|must\s+be)\s+(?:us\s+)?(?:citizen|permanent\s+resident|gc\s+holder)",
        r"visa\s+sponsorship\s+unavailable",
        r"(?:not\s+)?available\s+to\s+sponsor",
        r"restricted\s+to\s+(?:us\s+)?citizens",
    ]
    
    for pattern in no_sponsorship_patterns:
        if re.search(pattern, jd_lower):
            return False  # Sponsorship NOT available
    
    return True  # Sponsorship likely available


def _title_matches_target_role(title: str, target_roles: list[str], min_ratio: float = 0.65) -> bool:
    """
    Lenient fuzzy match between a job title and any target role.
    Uses rapidfuzz token_set_ratio scaled to 0–1. min_ratio ~0.65 = 65%+ similarity.
    """
    if not title or not target_roles:
        return False
    title_clean = tokenize_for_fuzz(title)
    if not title_clean:
        return False
    for role in target_roles:
        if not role:
            continue
        role_clean = tokenize_for_fuzz(str(role))
        if not role_clean:
            continue
        try:
            ratio = fuzz.token_set_ratio(title_clean, role_clean) / 100.0
        except Exception:
            ratio = 0.0
        if ratio >= min_ratio:
            return True
    return False


def keyword_matches_job(job: dict[str, Any], target_roles: list[str], resume_skills: set[str]) -> bool:
    """
    Check if job title/description matches target roles or resume skills.
    
    Args:
        job: Job dictionary with title, description
        target_roles: List of target role names (e.g., ["software engineer", "ml engineer"])
        resume_skills: Set of skills from resume (e.g., {"python", "tensorflow", "kubernetes"})
    
    Returns:
        True if job matches keywords
    """
    title = job.get("title") or ""
    title_lower = title.lower()
    desc_lower = (job.get("description") or "").lower()
    company_lower = (job.get("company") or "").lower()
    
    # Check if title approximately matches any target role (lenient fuzzy match)
    if _title_matches_target_role(title, target_roles):
        return True
    
    # Check if key skills appear in title or short description
    if resume_skills:
        # Look for skills in title (highest weight)
        title_words = set(title_lower.split())
        if len(title_words & resume_skills) >= 1:  # At least 1 skill match in title
            return True
        
        # Look for skills in description if available
        if desc_lower:
            desc_words = set(desc_lower.split())
            if len(desc_words & resume_skills) >= 2:  # At least 2 skills match in description
                return True
    
    return False


def fetch_job_description_from_url(url: str, timeout: int = 15, max_retries: int = 2) -> str:
    """
    Fetch full job description from a job URL with timeout and retry logic.
    Skips expired/filled jobs.
    
    Args:
        url: Job posting URL
        timeout: Request timeout in seconds (reduced for faster failure)
        max_retries: Number of retry attempts on failure
    
    Returns:
        Extracted job description text, or empty string if job is expired/error
    """
    import time
    
    for attempt in range(max_retries):
        try:
            import requests
            from bs4 import BeautifulSoup
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for visa/citizenship restrictions FIRST (higher priority)
            page_text_lower = response.text.lower()
            
            visa_restrictions = [
                'visa sponsorship is not available',
                'visa / work permit sponsorship is not available',
                'work permit sponsorship is not available',
                'no visa sponsorship',
                'does not sponsor visas',
                'will not sponsor work authorization',
                'must be authorized to work',
                'must be legally authorized to work',
                'us citizenship required',
                'u.s. citizenship required',
                'must be a us citizen',
                'must be a u.s. citizen',
                'citizenship is required',
                'active security clearance required',
                'must possess an active security clearance',
                'must possess and maintain an active',
                'requires us citizenship'
            ]
            
            for restriction in visa_restrictions:
                if restriction in page_text_lower:
                    print(f"  [fetch-skipped] Visa/citizenship restriction: {url[:60]}")
                    return ""  # Return empty to skip this job
            
            # Check for expired/filled job indicators
            expired_indicators = [
                'job has been filled',
                'job you are trying to apply for has been filled',
                'position has been filled',
                'no longer accepting applications',
                'job posting has expired',
                'this job is no longer available',
                'position is no longer available',
                'application deadline has passed',
                'job has closed',
                'posting has closed',
                'job not found',  # Google specific
                'this job may have been taken down',  # Google specific
                'job may have been removed',
                'position has been removed'
            ]
            
            for indicator in expired_indicators:
                if indicator in page_text_lower:
                    print(f"  [fetch-expired] Job filled/expired: {url[:60]}")
                    return ""  # Return empty to skip this job
            
            # Remove unwanted elements
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                tag.decompose()
            
            # Extract text
            text = soup.get_text(separator=' ', strip=True)
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Limit length
            if len(text) > 10000:
                text = text[:10000]
            
            return text
        
        except requests.Timeout:
            if attempt < max_retries - 1:
                print(f"  [fetch-timeout] Retry {attempt + 1}/{max_retries} for {url[:60]}...")
                time.sleep(1)  # Brief pause before retry
                continue
            else:
                print(f"  [fetch-timeout] Timeout after {max_retries} attempts: {url[:60]}")
                return ""
        
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"  [fetch-error] Retry {attempt + 1}/{max_retries}: {str(e)[:50]}")
                time.sleep(1)
                continue
            else:
                print(f"  [fetch-error] Failed after {max_retries} attempts: {url[:60]} - {str(e)[:50]}")
                return ""
        
        except Exception as e:
            print(f"  [fetch-error] Unexpected error for {url[:60]}: {str(e)[:50]}")
            return ""
    
    return ""


def enrich_jobs_with_descriptions(
    jobs: list[dict[str, Any]], 
    target_roles: list[str],
    resume_skills: set[str],
    max_workers: int = 5
) -> list[dict[str, Any]]:
    """
    Enrich jobs with full descriptions by:
    1. Filtering jobs that match keywords (title/skills)
    2. Fetching full description from job URL
    3. Returning enriched jobs
    
    Args:
        jobs: List of job dictionaries
        target_roles: Target role keywords
        resume_skills: Skills extracted from resume
        max_workers: Number of parallel workers
    
    Returns:
        List of jobs with descriptions
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Step 1: Filter jobs that match keywords
    print(f"\n[keyword-match] Checking {len(jobs)} jobs for keyword matches...")
    matching_jobs = []
    
    for job in jobs:
        if keyword_matches_job(job, target_roles, resume_skills):
            matching_jobs.append(job)
            title = job.get("title", "")[:50]
            company = job.get("company", "")
            print(f"  ✅ Match: {company} - {title}")
    
    print(f"[keyword-match] Found {len(matching_jobs)} jobs matching keywords")
    
    if not matching_jobs:
        print("[keyword-match] No matching jobs found")
        return jobs
    
    # Step 2: Fetch descriptions for matching jobs
    print(f"\n[fetch-desc] Fetching descriptions for {len(matching_jobs)} jobs (parallel workers: {max_workers})...")
    
    def fetch_one(job: dict[str, Any]) -> dict[str, Any]:
        url = job.get("url", "").strip()
        if not url or len(job.get("description", "")) > 500:
            # Already has description
            return job
        
        company = job.get("company", "")[:20]
        title = job.get("title", "")[:40]
        print(f"  [fetching] {company} - {title}")
        
        description = fetch_job_description_from_url(url)
        if description and len(description) > 200:
            job["description"] = description
            print(f"  ✅ Fetched {len(description)} chars for {company}")
        else:
            print(f"  ⚠️  Failed or short description for {company}")
        
        return job
    
    enriched = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, job): job for job in matching_jobs}
        
        for future in as_completed(futures):
            try:
                result = future.result()
                enriched.append(result)
            except Exception as e:
                job = futures[future]
                print(f"  ❌ Error processing {job.get('company')}: {e}")
                enriched.append(job)
    
    # Step 3: Filter out expired/failed jobs (empty descriptions) and merge
    enriched_valid = [job for job in enriched if job.get("description") and len(job.get("description", "")) > 100]
    enriched_expired = len(enriched) - len(enriched_valid)
    
    if enriched_expired > 0:
        print(f"[fetch-desc] Filtered out {enriched_expired} expired/invalid jobs")
    
    enriched_urls = {job["url"] for job in enriched_valid if job.get("url")}
    final_jobs = enriched_valid.copy()
    
    for job in jobs:
        if job.get("url") not in enriched_urls:
            final_jobs.append(job)
    
    print(f"[fetch-desc] Completed. {len(enriched_valid)} valid jobs enriched with descriptions\n")
    return final_jobs


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
        url_count = 0
        missing_url_count = 0
        for r in rows:
            url = r.get("url", "") or ""
            if url:
                url_count += 1
            else:
                missing_url_count += 1
                print(f"  [csv-debug] Missing URL for: {r.get('company', 'N/A')} - {r.get('title', 'N/A')[:50]}")
            w.writerow({
                "title": r.get("title", ""),
                "company": r.get("company", ""),
                "location": r.get("location", ""),
                "country": r.get("country", ""),
                "score": r.get("score", ""),
                "url": url,  # Ensure URL is written as-is
                "careers_url": r.get("careers_url", ""),
                "source": r.get("source", ""),
                "description": (r.get("description", "") or "").replace("\r", " ").replace("\n", " ")
            })
        print(f"  [csv-debug] Wrote {len(rows)} rows: {url_count} with URLs, {missing_url_count} without URLs")


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
    # Combined options from config
    free_opts = resolved_cfg.get("free_options") or {}
    selenium_opts = resolved_cfg.get("selenium_options") or {}

    selenium_sites = load_selenium_sites_from_opts(selenium_opts)

    fetched: list[dict[str, Any]] = []
    company_sources_cfg = resolved_cfg.get("company_sources") or {}
    hosted_jobs = fetch_company_source_jobs(
        company_sources_cfg,
        int(resolved_cfg.get("fetch_limit", 200)),
        country_filter=country,
    )
    fetched += hosted_jobs

    source_sites, source_companies = generate_company_source_sites(company_sources_cfg)
    if source_sites:
        selenium_sites.extend(source_sites)

    cfg_companies = resolved_cfg.get("companies") or []
    if source_companies:
        existing_lower = {c.lower() for c in cfg_companies if isinstance(c, str)}
        for slug in source_companies:
            if slug and slug.lower() not in existing_lower:
                cfg_companies.append(slug)
                existing_lower.add(slug.lower())
        resolved_cfg["companies"] = cfg_companies

    existing_site_companies: set[str] = set()
    for site in selenium_sites:
        if not isinstance(site, dict):
            continue
        comp = (site.get("company") or "").strip().lower()
        if comp:
            existing_site_companies.add(comp)

    missing_companies = [
        c for c in cfg_companies
        if c and c.strip().lower() not in existing_site_companies
    ]

    if (
        missing_companies
        and LLM_SELENIUM_SITE_BUILDER_AVAILABLE
        and generate_selenium_site_entries is not None
    ):
        print(f"[selenium-config] Generating site metadata for: {', '.join(missing_companies)}")
        new_sites = generate_selenium_site_entries(missing_companies)
        if new_sites:
            existing_keys = {
                (
                    (site.get("company") or "").strip().lower(),
                    (site.get("url") or "").strip().lower(),
                )
                for site in selenium_sites
                if isinstance(site, dict)
            }
            added_companies: list[str] = []
            for site in new_sites:
                if not isinstance(site, dict):
                    continue
                company_slug = (site.get("company") or "").strip().lower()
                url_slug = (site.get("url") or "").strip().lower()
                key = (company_slug, url_slug)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                selenium_sites.append(site)
                added_companies.append(company_slug or site.get("company", ""))

            existing_site_companies.update(
                [comp for comp in added_companies if comp]
            )

    if selenium_sites:
        site_companies = [
            s.get("company") for s in selenium_sites if isinstance(s, dict) and s.get("company")
        ]
        if site_companies:
            combined: list[str] = []
            seen_companies: set[str] = set()
            for name in list(cfg_companies) + site_companies:
                if not name:
                    continue
                normalized = str(name).strip()
                if not normalized:
                    continue
                key = normalized.lower()
                if key in seen_companies:
                    continue
                seen_companies.add(key)
                combined.append(normalized)
            cfg_companies = combined
            resolved_cfg["companies"] = combined
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

    resume_text, resume_structured = load_resume_data(resume_file)

    # Automatically enrich target_roles from structured resume (YAML) if available.
    # This pulls role titles from basics.label and work[].position/title, then merges
    # them with any target_roles already present in the config.
    if resume_structured and isinstance(resume_structured, dict):
        auto_roles: list[str] = []
        basics = resume_structured.get("basics") or {}
        label = basics.get("label") or basics.get("title")
        if isinstance(label, str) and label.strip():
            auto_roles.append(label.strip())
        work_entries = resume_structured.get("work") or []
        if isinstance(work_entries, list):
            for job in work_entries:
                if not isinstance(job, dict):
                    continue
                role = job.get("position") or job.get("title")
                if isinstance(role, str) and role.strip():
                    auto_roles.append(role.strip())

        # Merge with existing target_roles from config, de-duplicated (case-insensitive)
        existing_roles = resolved_cfg.get("target_roles") or []
        merged: list[str] = []
        seen_lower: set[str] = set()
        for role in list(existing_roles) + auto_roles:
            if not role:
                continue
            role_str = str(role).strip()
            if not role_str:
                continue
            key = role_str.lower()
            if key in seen_lower:
                continue
            seen_lower.add(key)
            merged.append(role_str)
        if merged:
            resolved_cfg["target_roles"] = merged

    # If no explicit query provided, derive it from the resume content
    if not query:
        try:
            query = build_query_from_resume(resume_text)
            print("[query] derived from resume:", query)
        except Exception:
            query = None

    # Fetch jobs according to chosen source(s)
    fetched: list[dict[str, Any]] = []
    job_assets: dict[str, dict[str, Any]] = {}

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

    # Free-source fetching removed; skip regardless of config.

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
        raw_sites = selenium_opts.get("sites")
        try:
            def _u(x):
                return x.get("url") if isinstance(x, dict) else str(x)
            print("[selenium] using sites:", [_u(s) for s in (raw_sites or [])])
        except Exception:
            pass
        if raw_sites:
            # Use parallel Selenium fetching for better performance
            from selenium_scraper import fetch_selenium_sites_parallel
            
            selenium_workers = min(3, len(raw_sites))  # Max 3 parallel drivers to avoid resource issues
            print(f"[selenium] Using parallel fetching with {selenium_workers} workers...")
            
            selenium_jobs = fetch_selenium_sites_parallel(
                raw_sites, 
                int(resolved_cfg.get("fetch_limit", 200)),
                max_workers=selenium_workers
            )
            
            # Debug: Log URL availability from Selenium
            selenium_with_urls = sum(1 for j in selenium_jobs if j.get("url"))
            selenium_without_urls = len(selenium_jobs) - selenium_with_urls
            print(f"[selenium-debug] Fetched {len(selenium_jobs)} jobs: {selenium_with_urls} with URLs, {selenium_without_urls} without URLs")
            if selenium_without_urls > 0:
                print(f"[selenium-debug] Jobs without URLs:")
                for j in selenium_jobs[:10]:  # Show first 10
                    if not j.get("url"):
                        print(f"  - {j.get('company', 'N/A')}: {j.get('title', 'N/A')[:50]} (source: {j.get('source', 'N/A')})")
            fetched += selenium_jobs

    # Country filter (lenient, allows 'Remote')
    if country:
        fetched = [j for j in fetched if _matches_country(j.get("location"), country)]

    # Enrich jobs with full descriptions based on keyword matching
    target_roles = resolved_cfg.get("target_roles", [])
    # Extract AUTOMOTIVE / SAFETY / SYSTEMS skills from the resume itself.
    resume_skills: set[str] = set()

    # 1) Prefer structured skills from YAML (input/resume.yml)
    if resume_structured and isinstance(resume_structured, dict):
        skills_section = resume_structured.get("skills") or []
        if isinstance(skills_section, list):
            for group in skills_section:
                if not isinstance(group, dict):
                    continue
                for kw in group.get("keywords") or []:
                    if not kw:
                        continue
                    kw_str = str(kw).strip()
                    if not kw_str:
                        continue
                    resume_skills.add(kw_str.lower())

    # 2) Fallback / complement: scan free text for common automotive/safety terms
    resume_lower = resume_text.lower()
    automotive_terms = {
        "automotive", "vehicle", "ev", "electric", "hybrid", "powertrain", "chassis",
        "braking", "steering", "ecu", "can", "lin", "flexray", "ethernet", "autosar",
        "embedded", "controller", "sensor", "actuator",
        "adas", "autonomous", "self-driving", "selfdriving", "autonomy",
        "perception", "sensor fusion", "sensor-fusion", "lane", "adaptive cruise",
        "functional safety", "system safety", "systems engineering", "systems engineer",
        "iso 26262", "iso26262", "asil", "hara", "fmea", "dfmea", "pfmea", "fta",
        "safety case", "safety-case", "sotif", "iec 61508", "iec61508", "arp4754",
        "requirements", "requirement", "doors", "polarion", "jama",
        "sysml", "uml", "mbse", "v-model", "verification", "validation", "integration", "test",
        "hil", "hardware-in-the-loop", "sil", "mil",
    }
    for term in automotive_terms:
        if term in resume_lower:
            resume_skills.add(term)

    # 3) Highlighted terms: any words/phrases in the original resume text that
    # contain uppercase letters (e.g., "ISO 26262", "ADAS", "Functional Safety").
    # These are treated as strong domain keywords.
    import re as _re_for_highlights
    highlighted: set[str] = set()
    # Split on whitespace, keep raw tokens to preserve capitalization and punctuation
    raw_tokens = (resume_text or "").split()
    for tok in raw_tokens:
        if not tok:
            continue
        # Strip common surrounding punctuation
        cleaned = tok.strip(".,;:()[]{}<>\"'")
        if len(cleaned) < 3:
            continue
        # Skip plain lowercase words (no uppercase at all)
        if not any(ch.isupper() for ch in cleaned):
            continue
        # Skip obvious sentence-start articles/pronouns
        if cleaned in {"The", "This", "That", "These", "Those", "And", "But"}:
            continue
        # Normalize to lowercase keyword
        highlighted.add(cleaned.lower())

    for kw in highlighted:
        resume_skills.add(kw)
    
    print(f"\n[keyword-match] Resume skills detected: {sorted(list(resume_skills)[:20])}")
    print(f"[keyword-match] Target roles: {target_roles[:10]}")
    
    # Enrich matching jobs with descriptions
    if target_roles or resume_skills:
        fetched = enrich_jobs_with_descriptions(
            fetched, 
            target_roles, 
            resume_skills,
            max_workers=resolved_cfg.get("parallel_workers", 5)
        )
    
    # Score and select
    print(f"\n[score] Scoring {len(fetched)} jobs with parallel workers...")
    
    from concurrent.futures import ThreadPoolExecutor as Executor, as_completed

    # If nothing was fetched, write empty outputs and exit cleanly.
    if not fetched:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        csv_path = out_file.with_suffix(".csv")
        write_csv([], csv_path)
        print(f"[score] No jobs fetched. Wrote empty outputs: {out_file} and {csv_path}")
        return
    
    def score_single_job(job: dict[str, Any]) -> dict[str, Any]:
        """Score a single job and return with score and country"""
        if not job.get("url"):
            print(f"[score-debug] Job without URL: {job.get('company', 'N/A')} - {job.get('title', 'N/A')[:50]} (source: {job.get('source', 'N/A')})")
        s = score_job(job, resume_text)
        # derive country value for CSV
        cval = "usa" if _matches_country(job.get("location"), "usa") else ""
        return {**job, "score": round(s, 2), "country": cval}
    
    # Parallel scoring
    scored = []
    max_score_workers = min(int(resolved_cfg.get("parallel_workers", 5) or 5), len(fetched))
    if max_score_workers < 1:
        max_score_workers = 1
    
    with Executor(max_workers=max_score_workers) as executor:
        future_to_job = {executor.submit(score_single_job, job): job for job in fetched}
        
        for idx, future in enumerate(as_completed(future_to_job), 1):
            try:
                result = future.result()
                scored.append(result)
                if idx % 10 == 0:  # Progress update every 10 jobs
                    print(f"  [score] Progress: {idx}/{len(fetched)} jobs scored")
            except Exception as e:
                job = future_to_job[future]
                print(f"  [score-error] Failed to score {job.get('company')}: {e}")
                # Add job with score 0 to not lose it
                scored.append({**job, "score": 0.0, "country": ""})
    
    print(f"[score] Completed scoring {len(scored)} jobs")
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: top_n]
    
    # Debug: Log URL availability in top N
    top_with_urls = sum(1 for j in top if j.get("url"))
    top_without_urls = len(top) - top_with_urls
    print(f"[score-debug] Top {len(top)} jobs: {top_with_urls} with URLs, {top_without_urls} without URLs")

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
            candidate_name = ""
            if resume_structured:
                candidate_name = (resume_structured.get("basics") or {}).get("name", "") or ""
            name_line = candidate_name.strip() or next(
                (ln.strip() for ln in resume_text.splitlines() if ln.strip()), "Candidate"
            )
            openai_cfg = resolved_cfg.get("openai") or {}
            use_openai = bool(openai_cfg.get("enabled"))
            openai_model = (openai_cfg.get("model") or "").strip()
            openai_key = (openai_cfg.get("api_key") or os.getenv("OPENAI_API_KEY") or "").strip()
            gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
            llm_provider = (os.getenv("LLM_PROVIDER") or ("openai" if openai_key else "gemini")).lower()
            
            # Initialize JobApplicationGenerator (preferred method)
            can_use_openai = use_openai and openai_key
            use_job_app_gen = bool(resolved_cfg.get("use_job_app_generator", True)) and JOB_APP_GENERATOR_AVAILABLE and (can_use_openai or gemini_key)
            job_app_gen = None
            gemini_fallback_attempted = False
            if use_job_app_gen:
                preferred_order = ["openai", "gemini"] if can_use_openai else ["gemini"]
                for provider in preferred_order:
                    try:
                        api_key = openai_key if provider == "openai" else gemini_key
                        if not api_key:
                            continue
                        job_app_gen = JobApplicationGenerator(api_key=api_key, provider=provider)
                        job_app_gen.set_resume(resume_text)
                        print(f"[jobgen] Using JobApplicationGenerator provider={provider}")
                        llm_provider = provider
                        break
                    except Exception as e:
                        print(f"[jobgen] Failed to initialize JobApplicationGenerator ({provider}): {e}")
                        job_app_gen = None
                if job_app_gen is None:
                    use_job_app_gen = False
            
            # Fallback: Initialize LLMCoverLetterJobDescription for cover letters  
            use_llm_resumer = False
            llm_resumer = None
            llm_resumer_ready = False
            use_llm_cover = False
            llm_cover = None

            if LLM_RESUMER_AVAILABLE and can_use_openai:
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
            
            if not use_job_app_gen and not use_llm_resumer and LLM_COVER_LETTER_AVAILABLE and can_use_openai:
                try:
                    llm_cover = LLMCoverLetterJobDescription(openai_key)
                    llm_cover.set_resume(resume_text)
                    use_llm_cover = True
                    print("[llmcover] Using LLMCoverLetterJobDescription (LangChain) for cover letter generation")
                except Exception as e:
                    print(f"[llmcover] Failed to initialize LLMCoverLetterJobDescription: {e}. Falling back.")
            
            # Initialize job description extractor (no embeddings needed)
            use_job_desc_extractor = False
            job_desc_extractor = None
            if JOB_DESC_EXTRACTOR_AVAILABLE and can_use_openai:
                try:
                    job_desc_extractor = JobDescriptionExtractor(openai_key)
                    use_job_desc_extractor = True
                    print("[extractor] Using LLM-based job description extractor (no embeddings)")
                except Exception as e:
                    print(f"[extractor] Failed to initialize: {e}. Will use basic extraction.")
            
            # Initialize LLMParser for job description enrichment (requires embeddings)
            use_llm_parser = False
            llm_parser = None
            skip_embedding_parser = os.getenv("SKIP_EMBEDDING_PARSER", "false").lower() == "true"
            if LLM_PARSER_AVAILABLE and can_use_openai and not skip_embedding_parser:
                try:
                    llm_parser = LLMParser(openai_key)
                    use_llm_parser = True
                    print("[parser] Using LLMParser (RAG-based) for job description parsing")
                except Exception as e:
                    print(f"[parser] Failed to initialize LLMParser: {e}. Falling back to extractor.")
            
            # Final fallback to CoverLetterBuilder
            builder = None
            if not use_job_app_gen and not use_llm_resumer and not use_llm_cover and COVER_LETTER_AVAILABLE:
                builder = CoverLetterBuilder(resume_text, name_line)
            
            # Auto-tailor resume and generate cover letter for jobs with score > 40
            auto_tailor = bool(resolved_cfg.get("auto_tailor_resume", False))
            tailor_threshold = int(resolved_cfg.get("tailor_threshold", 40))
            enforced_tailor_threshold = max(tailor_threshold, 40)
            
            print(f"[config] auto_tailor_resume: {auto_tailor}")
            print(f"[config] tailor_threshold: {tailor_threshold}")
            
            if not auto_tailor:
                print("[config] ⚠️  WARNING: auto_tailor_resume is FALSE in config!")
                print("[config] Resumes and cover letters will NOT be generated!")
                print("[config] Set 'auto_tailor_resume': true in your config.json")
            tailored_resumes_dir = out_file.parent / "tailored_resumes"
            if auto_tailor:
                tailored_resumes_dir.mkdir(parents=True, exist_ok=True)
            
            # Filter jobs by score threshold FIRST to avoid wasting time
            score_threshold = float(resolved_cfg.get("min_score", 60))
            target_locations = resolved_cfg.get("target_locations", [])
            top_per_company = bool(resolved_cfg.get("top_per_company", False))
            top_per_company_limit = int(resolved_cfg.get("top_per_company_limit", 1) or 1)
            if top_per_company_limit < 1:
                top_per_company_limit = 1

            # For threshold filtering, always allow jobs whose TITLE approximately matches
            # any target role (lenient fuzzy match), even if their fuzzy score is slightly
            # below min_score. This ensures roles like "System Safety Engineer" or
            # "Functional Safety Engineer" are never dropped.
            raw_target_roles = resolved_cfg.get("target_roles", []) or []

            def _passes_score_or_title_match(job: dict[str, Any]) -> bool:
                s = float(job.get("score", 0) or 0)
                if s >= score_threshold:
                    return True
                title_val = job.get("title") or ""
                if _title_matches_target_role(title_val, raw_target_roles, min_ratio=0.6):
                    return True
                return False

            top_window = top[:top_n]
            print(f"[filter] Starting with {len(top_window)} jobs")
            print(f"[filter] Filtering jobs with score >= {score_threshold} (or direct title match to target_roles)")
            
            # Debug: Log URL availability before filtering
            jobs_with_urls = sum(1 for j in top_window if j.get("url"))
            jobs_without_urls = len(top_window) - jobs_with_urls
            print(f"[filter-debug] Before filtering: {jobs_with_urls} jobs with URLs, {jobs_without_urls} without URLs")
            
            if target_locations:
                print(f"[filter] Target locations: {', '.join(target_locations)}")
            if top_per_company:
                print(f"[filter] Top per company mode: Will select only highest scoring job from each company")
            
            # Filter by score (with title-based override for strong target role matches)
            filtered_jobs = [j for j in top_window if _passes_score_or_title_match(j)]
            print(f"[filter] After score filter: {len(filtered_jobs)} jobs (removed {len(top_window) - len(filtered_jobs)})")
            
            # Debug: Log URL availability after score filter
            filtered_with_urls = sum(1 for j in filtered_jobs if j.get("url"))
            filtered_without_urls = len(filtered_jobs) - filtered_with_urls
            print(f"[filter-debug] After score filter: {filtered_with_urls} jobs with URLs, {filtered_without_urls} without URLs")
            
            # Debug: Show score distribution and sample
            print(f"\n[filter-debug] SCORE DISTRIBUTION:")
            all_scores = [j.get("score", 0) for j in top_window]
            if all_scores:
                avg_score = sum(all_scores) / len(all_scores)
                max_score = max(all_scores)
                min_score = min(all_scores)
                print(f"  - Average score: {avg_score:.2f}")
                print(f"  - Max score: {max_score:.2f}")
                print(f"  - Min score: {min_score:.2f}")
                print(f"  - Score threshold: {score_threshold}")
                print(f"  - Jobs above threshold: {len(filtered_jobs)}/{len(top_window)}")
            
            if filtered_jobs:
                print(f"\n[filter] ✅ Sample jobs after score filter:")
                for j in filtered_jobs[:5]:
                    url_status = "✅" if j.get("url") else "❌ NO URL"
                    print(f"  - {j.get('company', 'N/A')}: {j.get('title', 'N/A')[:50]} | Score: {j.get('score', 0):.1f} | {url_status}")
            else:
                print(f"\n[filter] ❌ NO JOBS ABOVE SCORE THRESHOLD!")
                print(f"[filter] Top 5 jobs (all below threshold):")
                for j in top[:5]:
                    print(f"  - {j.get('company', 'N/A')}: {j.get('title', 'N/A')[:50]} | Score: {j.get('score', 0):.1f}")
                print(f"\n[filter] 💡 ACTION: Lower min_score in config.json to {min_score:.1f} or lower")

            # Track best job per company from the entire candidate set (top 100) for fallback usage
            company_targets: list[str] = []
            try:
                company_targets = [
                    (c or "").lower().strip()
                    for c in resolved_cfg.get("companies", [])
                    if c and str(c).strip()
                ]
            except Exception:
                company_targets = []

            def _job_company_key(job: dict[str, Any]) -> str:
                company_key = (job.get("company") or "").lower().strip()
                if not company_key or company_key in ("not specified", "not specified."):
                    source = job.get("source", "")
                    if ":" in source:
                        company_key = source.split(":")[-1].strip().lower()
                return company_key

            best_jobs_by_company: dict[str, list[dict[str, Any]]] = {}
            for job in top_window:
                company_key = _job_company_key(job)
                if not company_key:
                    continue
                bucket = best_jobs_by_company.setdefault(company_key, [])
                bucket.append(job)

            for bucket in best_jobs_by_company.values():
                bucket.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            # Filter by target roles if provided (LENIENT matching with fuzzy matching)
            target_roles = [role.strip() for role in resolved_cfg.get("target_roles", []) if role and role.strip()]
            if target_roles:
                print(f"[filter] Target roles (LENIENT mode): {', '.join(target_roles[:6])}" + (" ..." if len(target_roles) > 6 else ""))

                def _normalize_role_text(text: str) -> str:
                    """Lowercase and strip punctuation for consistent comparisons."""
                    return re.sub(r"[^a-z0-9\\s]", " ", text.lower()).strip()

                normalized_roles = [_normalize_role_text(role) for role in target_roles if _normalize_role_text(role)]
                
                # Generic keywords that indicate technical roles (for fallback matching)
                generic_tech_keywords = [
                    "engineer", "developer", "architect", "manager", "lead",
                    "senior", "principal", "staff", "staff engineer", "staff developer",
                    "security", "devops", "platform", "infrastructure", "backend",
                    "frontend", "full stack", "data", "ml", "ai", "analytics"
                ]
                
                role_filtered_jobs = []
                removed_titles = []

                for job in filtered_jobs:
                    raw_title = (job.get("title") or "").strip()
                    title_norm = _normalize_role_text(raw_title)

                    if not title_norm:
                        removed_titles.append(raw_title or "(missing title)")
                        continue

                    title_words = set(title_norm.split())
                    matched = False
                    match_type = ""

                    # Method 1: Direct substring match (e.g., "software engineer" in "senior software engineer")
                    for role_norm in normalized_roles:
                        role_words = [w for w in role_norm.split() if w]
                        if not role_words:
                            continue

                        if role_norm in title_norm:
                            matched = True
                            match_type = "exact_substring"
                            break

                        # All role words present somewhere in title, order agnostic
                        if all(word in title_words for word in role_words):
                            matched = True
                            match_type = "all_words_present"
                            break

                    # Method 2: Fuzzy match - if title contains any target role words + "engineer/developer/etc"
                    if not matched:
                        # Check if title contains keywords from target roles (lenient)
                        for role_norm in normalized_roles:
                            # Get first meaningful word from role (e.g., "software" from "software engineer")
                            role_parts = [w for w in role_norm.split() if len(w) > 2]
                            if role_parts and role_parts[0] in title_words:
                                # And has a tech keyword like "engineer"
                                if any(keyword in title_norm for keyword in generic_tech_keywords):
                                    matched = True
                                    match_type = "fuzzy_keyword"
                                    break

                    # Method 3: Generic tech role match (fallback for any engineer/developer/etc role)
                    if not matched:
                        if any(keyword in title_norm for keyword in generic_tech_keywords):
                            matched = True
                            match_type = "generic_tech_role"

                    if matched:
                        role_filtered_jobs.append(job)
                    else:
                        removed_titles.append(raw_title or "(missing title)")

                if role_filtered_jobs:
                    removed_count = len(filtered_jobs) - len(role_filtered_jobs)
                    print(f"[filter] After role filter (LENIENT): {len(role_filtered_jobs)} jobs (removed {removed_count})")
                    if removed_titles:
                        sample_removed = ", ".join(removed_titles[:3])
                        print(f"[filter] Skipped non-technical roles: {sample_removed}" + ("..." if len(removed_titles) > 3 else ""))
                    filtered_jobs = role_filtered_jobs
                else:
                    print(f"[filter] ⚠️  Role filter too strict - no jobs matched. Accepting all {len(filtered_jobs)} jobs.")

            # Filter by location if specified (AFTER fetching, not in URL)
            if target_locations and filtered_jobs:
                location_matched_jobs = []
                for j in filtered_jobs:
                    job_location = (j.get("location") or "").lower()
                    # Check if job location contains any of the target locations
                    for target_loc in target_locations:
                        if target_loc.lower() in job_location:
                            location_matched_jobs.append(j)
                            break
                
                if location_matched_jobs:
                    print(f"[filter] After location filter: {len(location_matched_jobs)} jobs (removed {len(filtered_jobs) - len(location_matched_jobs)})")
                    filtered_jobs = location_matched_jobs
                else:
                    print(f"[filter] WARNING: No jobs match target locations. Processing all {len(filtered_jobs)} jobs.")

            # Ensure each configured company has at least one job (fallback)
            if company_targets:
                company_counts: dict[str, int] = {}
                for job in filtered_jobs:
                    company_key = _job_company_key(job)
                    if company_key:
                        company_counts[company_key] = company_counts.get(company_key, 0) + 1

                fallback_added: list[str] = []
                for company_key in company_targets:
                    if not company_key:
                        continue
                    needed = top_per_company_limit if top_per_company else 1
                    existing = company_counts.get(company_key, 0)
                    if existing >= needed:
                        continue
                    candidates = best_jobs_by_company.get(company_key, [])
                    if not candidates:
                        continue
                    for candidate in candidates:
                        candidate_id = candidate.get("url") or candidate.get("id") or ""
                        if candidate_id and any(candidate_id == (job.get("url") or job.get("id") or "") for job in filtered_jobs):
                            continue
                        filtered_jobs.append(candidate)
                        existing += 1
                        company_counts[company_key] = existing
                        fallback_added.append(f"{company_key} ({candidate.get('title', 'N/A')} | score {candidate.get('score', 0):.1f})")
                        if existing >= needed:
                            break

                if fallback_added:
                    print(f"[filter] Fallback added jobs for: {', '.join(fallback_added)}")
            
            # If top_per_company mode, keep up to N highest scoring jobs from each company
            if top_per_company and filtered_jobs:
                company_map: dict[str, list[dict[str, Any]]] = {}
                for j in filtered_jobs:
                    # Get company name, fallback to source if not specified
                    company = _job_company_key(j)
                    if not company:
                        continue
                    bucket = company_map.setdefault(company, [])
                    bucket.append(j)

                limited_jobs: list[dict[str, Any]] = []
                for company, jobs in company_map.items():
                    jobs.sort(key=lambda x: x.get("score", 0), reverse=True)
                    limited_jobs.extend(jobs[:top_per_company_limit])

                filtered_jobs = sorted(limited_jobs, key=lambda x: x.get("score", 0), reverse=True)
                print(f"[filter] After top-per-company: {len(filtered_jobs)} jobs from {len(company_map)} companies (limit {top_per_company_limit})")
            
            if not filtered_jobs:
                print(f"[filter] WARNING: No jobs above score threshold {score_threshold}. Lowering to 40.")
                filtered_jobs = [j for j in top[:100] if j.get("score", 0) >= 40]
                
                # Try location filtering again with lowered threshold
                if target_locations and filtered_jobs:
                    location_matched_jobs = []
                    for j in filtered_jobs:
                        job_location = (j.get("location") or "").lower()
                        for target_loc in target_locations:
                            if target_loc.lower() in job_location:
                                location_matched_jobs.append(j)
                                break
                    if location_matched_jobs:
                        filtered_jobs = location_matched_jobs
                
                # Apply top per company again if enabled
                if top_per_company and filtered_jobs:
                    company_best = {}
                    for j in filtered_jobs:
                        # Get company name, fallback to source if not specified
                        company = (j.get("company") or "").lower().strip()
                        if not company or company == "not specified" or company == "not specified.":
                            # Try to extract from source (e.g., "selenium:google" -> "google")
                            source = j.get("source", "")
                            if ":" in source:
                                company = source.split(":")[-1].strip()
                        
                        if not company:
                            continue
                        
                        score = j.get("score", 0)
                        if company not in company_best or score > company_best[company]["score"]:
                            company_best[company] = j
                    filtered_jobs = list(company_best.values())
                    filtered_jobs.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            print(f"[filter] Processing {len(filtered_jobs)} jobs (out of {len(top[:100])} total)")
            
            if not filtered_jobs:
                print(f"[filter] ❌ NO JOBS TO PROCESS after all filters!")
                print(f"[filter] This means no cover letters or resumes will be generated.")
            else:
                print(f"[filter] ✅ Will generate cover letters and resumes for these {len(filtered_jobs)} jobs:")
                for idx, j in enumerate(filtered_jobs, 1):
                    print(f"  {idx}. {j.get('company', 'N/A')} - {j.get('title', 'N/A')[:50]} (score: {j.get('score', 0):.1f})")
            
            # Pre-fetch job descriptions in parallel for speed
            def fetch_job_desc(job):
                """Fetch and enrich job description in parallel."""
                job_url = (job.get("url") or "").strip()
                company = _normalize_meta_field(job.get("company"))
                role = _normalize_meta_field(job.get("title"))
                company_label = company or "Company"
                role_label = role or "Role"
                jd_text = (job.get("description") or "").strip()
                
                # Debug: Log URL status
                if not job_url:
                    print(f"  [parallel-fetch] {company_label}: ⚠️ NO URL in job data")
                    print(f"  [parallel-fetch] {company_label}: Job keys: {list(job.keys())}")
                    print(f"  [parallel-fetch] {company_label}: Job data: {str(job)[:200]}")
                    return job
                
                print(f"  [parallel-fetch] {company_label}: Starting fetch from {job_url}")
                
                # ALWAYS try HTML parser first (best quality) - increased timeout
                if LLM_JOB_HTML_PARSER_AVAILABLE and use_openai and openai_key:
                    try:
                        headers = {
                            "User-Agent": (
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                            )
                        }
                        resp = requests.get(job_url, timeout=60, headers=headers)  # Increased from 30 to 60
                        resp.raise_for_status()
                        html_content = resp.text
                        job_html_parser = LLMJobHTMLParser(openai_key)
                        job_html_parser.set_body_html(html_content)
                        extracted_desc = job_html_parser.extract_job_description()
                        if extracted_desc and len(extracted_desc) > 100:
                            job["description"] = extracted_desc.strip()
                            print(f"  [parallel-fetch] {company_label}: ✅ {len(extracted_desc)} chars (HTML parser)")
                            return job
                        else:
                            print(f"  [parallel-fetch] {company_label}: HTML parser returned short/empty result ({len(extracted_desc) if extracted_desc else 0} chars)")
                    except requests.exceptions.Timeout:
                        print(f"  [parallel-fetch] {company_label}: ⚠️ Timeout fetching {job_url[:60]}...")
                    except requests.exceptions.RequestException as e:
                        print(f"  [parallel-fetch] {company_label}: ⚠️ Request failed: {type(e).__name__}: {e}")
                    except Exception as e:
                        print(f"  [parallel-fetch] {company_label}: HTML parser failed: {type(e).__name__}: {e}")
                
                # Fallback to plain text fetch (strip HTML tags) - increased timeout
                try:
                    fallback_desc = fetch_job_description_plain(job_url)
                    if fallback_desc and len(fallback_desc) > 100:
                        job["description"] = fallback_desc
                        print(f"  [parallel-fetch] {company_label}: ✅ {len(fallback_desc)} chars (plain text)")
                        return job
                    else:
                        print(f"  [parallel-fetch] {company_label}: Plain text fetch returned short/empty result ({len(fallback_desc) if fallback_desc else 0} chars)")
                except requests.exceptions.Timeout:
                    print(f"  [parallel-fetch] {company_label}: ⚠️ Timeout in plain text fetch")
                except Exception as e:
                    print(f"  [parallel-fetch] {company_label}: Plain fetch failed: {type(e).__name__}: {e}")
                
                # Try Playwright for JavaScript-rendered content (e.g., Meta careers)
                try:
                    print(f"  [parallel-fetch] {company_label}: Trying Playwright for JS-rendered content...")
                    pw_desc = fetch_job_description_with_playwright(job_url)
                    if pw_desc and len(pw_desc) > 100:
                        job["description"] = pw_desc
                        print(f"  [parallel-fetch] {company_label}: ✅ {len(pw_desc)} chars (Playwright)")
                        return job
                    else:
                        print(f"  [parallel-fetch] {company_label}: Playwright returned short/empty result ({len(pw_desc) if pw_desc else 0} chars)")
                except Exception as e:
                    print(f"  [parallel-fetch] {company_label}: Playwright failed: {type(e).__name__}")
                
                # If still no description, create minimal one from title/company
                if not job.get("description") or len(job.get("description", "")) < 50:
                    company_phrase = f" at {company_label}" if company_label else ""
                    minimal_desc = f"Position: {role_label}{company_phrase}. Application URL: {job_url}"
                    job["description"] = minimal_desc
                    print(f"  [parallel-fetch] {company_label}: ⚠️ Using minimal description ({len(minimal_desc)} chars)")
                
                # Ensure URL is preserved
                job["url"] = job_url
                return job
            
            # Parallel fetch job descriptions
            if filtered_jobs:
                parallel_workers = int(resolved_cfg.get("parallel_workers", 5))
                parallel_workers = min(parallel_workers, len(filtered_jobs))  # Don't create more workers than jobs
                print(f"[parallel] Pre-fetching job descriptions with {parallel_workers} workers...")
                with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                    # Submit all jobs for parallel fetching
                    future_to_idx = {executor.submit(fetch_job_desc, j): i for i, j in enumerate(filtered_jobs)}
                    
                    # Wait for all to complete and update the jobs list
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        try:
                            updated_job = future.result()
                            filtered_jobs[idx] = updated_job
                        except Exception as e:
                            print(f"  [parallel-fetch] Error processing job {idx}: {e}")
                
                print(f"[parallel] Job description fetching complete!")
            
            # Track filtering statistics
            filter_stats = {
                "total": len(filtered_jobs),
                "sponsorship_blocked": 0,
                "created": 0,
            }
            
            for idx, j in enumerate(filtered_jobs):
                score = j.get("score", 0)
                company = _normalize_meta_field(j.get("company"))
                if not company:
                    source = j.get("source", "")
                    if ":" in source:
                        company = _normalize_meta_field(source.split(":")[-1].strip().title())
                        j["company"] = company
                company_label = company or "Company"
                
                role = _normalize_meta_field(j.get("title"))
                if not role and j.get("original_title"):
                    role = _normalize_meta_field(j.get("original_title"))
                role_label = role or "Role"
                
                jd_text = (j.get("description") or "").strip()
                job_url = (j.get("url") or "").strip()
                base = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{company_label}_{role_label}")[:80]
                key_primary = job_url or base
                assets = job_assets.setdefault(key_primary, {"base": base})
                if job_url:
                    job_assets[job_url] = assets
                assets["company"] = company
                assets["role"] = role
                llm_resume_generated = False
                llm_resume_text = None
                builder_tailored = builder
                should_force_llm_resume = False
                
                html_parsed_info = {}
                if (
                    job_url
                    and LLM_JOB_HTML_PARSER_AVAILABLE
                    and use_openai
                    and openai_key
                ):
                    try:
                        print(f"  [parser-html] Fetching job posting for {company_label}...")
                        headers = {
                            "User-Agent": (
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                            )
                        }
                        resp = requests.get(job_url, timeout=60, headers=headers)  # Increased from 30 to 60
                        resp.raise_for_status()
                        html_content = resp.text
                        job_html_parser = LLMJobHTMLParser(openai_key)
                        job_html_parser.set_body_html(html_content)
                        extracted_desc = job_html_parser.extract_job_description()
                        if extracted_desc:
                            jd_text = extracted_desc.strip()
                            j["description"] = jd_text
                            print(
                                f"  [parser-html] Extracted description ({len(jd_text)} chars) for {company_label}"
                            )
                        else:
                            print(
                                f"  [parser-html] No description extracted for {company_label}"
                            )

                        try:
                            html_parsed_info = {
                                "company": job_html_parser.extract_company_name(),
                                "role": job_html_parser.extract_role(),
                                "location": job_html_parser.extract_location(),
                                "description": job_html_parser.extract_job_description(),
                                "required_skills": job_html_parser._extract_information(
                                    "What are the required skills and responsibilities?",
                                    "Responsibilities requirements"
                                ),
                            }
                        except Exception:
                            html_parsed_info = {}
                    except Exception as e:
                        print(
                            f"  [parser-html] Failed to extract description for {company_label}: {e}"
                        )

                if html_parsed_info:
                    if html_parsed_info.get("company"):
                        company_from_html = _normalize_meta_field(html_parsed_info["company"])
                        if company_from_html:
                            company = company_from_html
                            company_label = company
                            j["company"] = company
                    if html_parsed_info.get("role"):
                        role_from_html = _normalize_meta_field(html_parsed_info["role"])
                        if role_from_html:
                            role = role_from_html
                            role_label = role
                            j["title"] = role
                    if html_parsed_info.get("location"):
                        j["location"] = html_parsed_info["location"]
                    if html_parsed_info.get("description") and not jd_text:
                        jd_text = html_parsed_info["description"].strip()
                        j["description"] = jd_text
                    if html_parsed_info.get("required_skills"):
                        j["parsed_required_skills"] = html_parsed_info["required_skills"].strip()
                    assets["company"] = company
                    assets["role"] = role
                    company_label = company or company_label
                    role_label = role or role_label

                if (not jd_text or len(jd_text) < 200) and job_url:
                    print(f"  [fetch] Job description too short, trying direct fetch from URL...")
                    fallback_desc = fetch_job_description_plain(job_url)
                    if fallback_desc:
                        jd_text = fallback_desc
                        j["description"] = jd_text
                        print(f"  [fetch] Fetched {len(jd_text)} chars from URL")
                
                # If still no description and we have URL, use LLM extractor to fetch and parse
                if (not jd_text or len(jd_text) < 100) and job_url and use_job_desc_extractor:
                    try:
                        print(f"  [extractor] Fetching page and extracting with LLM...")
                        import requests
                        headers = {
                            "User-Agent": (
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                            )
                        }
                        resp = requests.get(job_url, timeout=60, headers=headers)  # Increased from 30 to 60
                        resp.raise_for_status()
                        extracted = job_desc_extractor.extract_job_description(resp.text, company, role)
                        if extracted and extracted.get("description"):
                            # Build a comprehensive description from all extracted parts
                            desc_parts = []
                            if extracted.get("description"):
                                desc_parts.append(extracted["description"])
                            if extracted.get("responsibilities"):
                                desc_parts.append("\n\nResponsibilities:\n" + extracted["responsibilities"])
                            if extracted.get("minimum_qualifications"):
                                desc_parts.append("\n\nMinimum Qualifications:\n" + extracted["minimum_qualifications"])
                            if extracted.get("preferred_qualifications"):
                                desc_parts.append("\n\nPreferred Qualifications:\n" + extracted["preferred_qualifications"])
                            
                            jd_text = "\n".join(desc_parts)
                            j["description"] = jd_text
                            print(f"  [extractor] Extracted comprehensive JD: {len(jd_text)} chars")
                    except Exception as e:
                        print(f"  [extractor] Failed to fetch/extract from URL: {e}")

                # Debug: log job details with detailed info
                has_url = "✅" if job_url else "❌ NO URL"
                has_desc = f"✅ {len(jd_text)} chars" if jd_text else "❌ NO DESC"
                print(f"[cover] {idx+1}/100: {company_label} - {role_label} | Score: {score:.1f} | URL: {has_url} | Desc: {has_desc}")
                
                # Check if visa sponsorship is available (disabled by default)
                sponsorship_check_enabled = False  # Set to True to enable sponsorship filtering
                has_sponsorship = check_sponsorship_available(jd_text, check_enabled=sponsorship_check_enabled)
                if not has_sponsorship:
                    print(f"  [skip] ⏭️ ❌ SPONSORSHIP: No visa sponsorship available for this position")
                    print(f"       Company: {company_label} | Role: {role_label} | Score: {score}")
                    filter_stats["sponsorship_blocked"] += 1
                    continue
                
                # If we STILL don't have a description, create a minimal one from title/company
                if not jd_text or len(jd_text) < 50:
                    print(f"  WARNING: Job description too short or empty for {company}")
                    print(f"  DEBUG: auto_tailor={auto_tailor}, use_job_app_gen={use_job_app_gen}")
                    print(f"  DEBUG: Job URL: {job_url}")
                    
                    # Generate a minimal description to enable LLM generation
                    if not jd_text:
                        jd_text = f"Position: {role} at {company}. Location: {j.get('location', 'Not specified')}."
                        if job_url:
                            jd_text += f" Application URL: {job_url}"
                        print(f"  [fallback] Created minimal JD from metadata: {len(jd_text)} chars")
                        j["description"] = jd_text
                
                # Use LLM-based extractor (no embeddings) if RAG parser failed or unavailable
                parsed_info = dict(html_parsed_info)
                if use_job_desc_extractor and jd_text and not use_llm_parser:
                    try:
                        print(f"  [extractor] Extracting structured info for {company}...")
                        extracted = job_desc_extractor.extract_job_description(jd_text, company, role)
                        
                        # Convert extracted format to parsed_info format
                        if extracted:
                            parsed_info["description"] = extracted.get("description", "")
                            parsed_info["required_skills"] = extracted.get("responsibilities", "") + "\n" + extracted.get("minimum_qualifications", "")
                            parsed_info["preferred_skills"] = extracted.get("preferred_qualifications", "")
                            
                            # Save extracted info
                            if extracted.get("description"):
                                parsed_dir = out_file.parent / "parsed_jobs"
                                parsed_dir.mkdir(parents=True, exist_ok=True)
                                parsed_path = parsed_dir / f"extracted_{base}.txt"
                                with open(parsed_path, "w", encoding="utf-8") as f:
                                    f.write(extracted.get("raw_structured", ""))
                                print(f"  [extractor] Saved structured info for {company}")
                    except Exception as e:
                        print(f"  [extractor] Error extracting {company}: {e}")
                
                # Use LLMParser to enrich job information if available
                if use_llm_parser and jd_text:
                    try:
                        print(f"  [parser] Parsing job description for {company}...")
                        parsed_from_text = llm_parser.parse_job_from_text(jd_text)
                        if parsed_from_text:
                            parsed_info.update(parsed_from_text)
                        
                        # Update job fields with parsed information if better
                        if parsed_info.get("company") and parsed_info["company"] != "Not specified":
                            company = parsed_info["company"]
                            j["company"] = company
                        if parsed_info.get("role") and parsed_info["role"] != "Not specified":
                            role = parsed_info["role"]
                            j["title"] = role
                        
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
                        # Fallback to extractor if parser fails
                        if use_job_desc_extractor and not parsed_info:
                            try:
                                print(f"  [extractor] Trying extractor as fallback for {company}...")
                                extracted = job_desc_extractor.extract_job_description(jd_text, company, role)
                                if extracted:
                                    parsed_info["description"] = extracted.get("description", "")
                                    parsed_info["required_skills"] = extracted.get("responsibilities", "") + "\n" + extracted.get("minimum_qualifications", "")
                                    parsed_info["preferred_skills"] = extracted.get("preferred_qualifications", "")
                            except Exception:
                                pass
                
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
                            assets["cover_letter"] = str(txt_path)
                            print(f"  [llm] Cover letter saved for {company} using LLMResumer")
                    except Exception as e:
                        print(f"  [llm] Cover letter generation failed for {company}: {e}")
                
                # Method 1: JobApplicationGenerator (unified, preferred)
                jobgen_success = False
                jd_len = len(jd_text)
                print(f"  [debug] Job processing for {company}:")
                print(f"    - use_job_app_gen: {use_job_app_gen}")
                print(f"    - auto_tailor: {auto_tailor}")
                print(f"    - jd_len: {jd_len}")
                print(f"    - job_url: {job_url}")
                
                if use_job_app_gen and auto_tailor and jd_text:
                    try:
                        print(f"\n  ✅ RESUME GENERATION ATTEMPT:")
                        print(f"     - use_job_app_gen: {use_job_app_gen}")
                        print(f"     - auto_tailor: {auto_tailor}")
                        print(f"     - jd_text length: {len(jd_text)} chars")
                        print(f"     - company: {company}")
                        print(f"     - role: {role}")
                        print(f"  [jobgen] Generating application package for {company}...")
                        try:
                            result = job_app_gen.generate_application_package(jd_text, company, role, parallel=True)
                        except Exception as e:
                            msg = str(e).lower()
                            if ("insufficient_quota" in msg or "exceeded your current quota" in msg or "429" in msg) and gemini_key and not gemini_fallback_attempted:
                                print("  [jobgen] OpenAI quota exceeded. Attempting Gemini fallback...")
                                try:
                                    fallback_gen = JobApplicationGenerator(api_key=gemini_key, provider="gemini")
                                    fallback_gen.set_resume(resume_text)
                                    job_app_gen = fallback_gen
                                    llm_provider = "gemini"
                                    gemini_fallback_attempted = True
                                    result = job_app_gen.generate_application_package(jd_text, company, role, parallel=True)
                                except Exception as fallback_exc:
                                    print(f"  [jobgen] Gemini fallback failed: {fallback_exc}")
                                    raise
                            else:
                                raise
                        
                        # Save tailored resume (TXT)
                        if result.get("resume"):
                            resume_path = tailored_resumes_dir / f"resume_{base}.txt"
                            with open(resume_path, "w", encoding="utf-8") as f:
                                f.write(result["resume"])
                            assets["resume"] = str(resume_path)
                            filter_stats["created"] += 1
                            print(f"  [jobgen] ✅ Resume saved: {resume_path.name}")
                            
                            # Generate PDF and DOCX versions using helper
                            # Read from saved file to ensure exact match
                            try:
                                from resume_upload_helper import create_and_save_resume_files
                                
                                # Read exact content from saved file to ensure PDF matches text file exactly
                                with open(resume_path, "r", encoding="utf-8") as f:
                                    exact_resume_content = f.read()
                                
                                file_paths = create_and_save_resume_files(
                                    resume_text=exact_resume_content,  # Use exact file content
                                    output_dir=str(tailored_resumes_dir),
                                    job_title=role,
                                    company_name=company,
                                    candidate_name="",  # Will be extracted from resume
                                    formats=['pdf', 'docx']  # Generate both formats
                                )
                                if file_paths.get('docx'):
                                    assets["resume_docx"] = file_paths['docx']
                                    print(f"  [jobgen] ✅ Resume DOCX saved: {os.path.basename(file_paths['docx'])}")
                                if file_paths.get('pdf'):
                                    assets["resume_pdf"] = file_paths['pdf']
                                    print(f"  [jobgen] ✅ Resume PDF saved: {os.path.basename(file_paths['pdf'])}")
                            except Exception as pdf_err:
                                print(f"  [jobgen] ⚠️  Document generation failed: {pdf_err}")
                        
                        # Save cover letter (TXT)
                        if result.get("cover_letter"):
                            txt_path = letters_dir / f"cover_{base}.txt"
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(result["cover_letter"])
                            assets["cover_letter"] = str(txt_path)
                            print(f"  [jobgen] ✅ Cover letter saved: {txt_path.name}")
                            
                            # Generate PDF version using helper
                            try:
                                from resume_upload_helper import create_and_save_cover_letter_pdf
                                pdf_path_abs = create_and_save_cover_letter_pdf(
                                    cover_letter_text=result["cover_letter"],
                                    output_dir=str(letters_dir),
                                    job_title=role,
                                    company_name=company,
                                    candidate_name="",
                                    candidate_email="",
                                    candidate_phone=""
                                )
                                if pdf_path_abs:
                                    assets["cover_letter_pdf"] = pdf_path_abs
                                    print(f"  [jobgen] ✅ Cover letter PDF saved: {os.path.basename(pdf_path_abs)}")
                            except Exception as pdf_err:
                                print(f"  [jobgen] ⚠️  PDF generation failed: {pdf_err}")
                        
                        # Optionally save job summary
                        if result.get("job_summary"):
                            summary_dir = out_file.parent / "job_summaries"
                            summary_dir.mkdir(parents=True, exist_ok=True)
                            summary_path = summary_dir / f"summary_{base}.txt"
                            with open(summary_path, "w", encoding="utf-8") as f:
                                f.write(result["job_summary"])
                            assets["job_summary"] = str(summary_path)
                            print(f"  [jobgen] ✅ Job summary saved: {summary_path.name}")
                        
                        jobgen_success = True
                    except Exception as e:
                        print(f"  [jobgen] ❌ Error for {company}: {e}. Falling back.")
                elif not jd_text:
                    print(f"  [jobgen] ⚠️  Skipping {company} - No job description available")
                elif not auto_tailor:
                    print(f"  [jobgen] ⚠️  Skipping {company} - auto_tailor is disabled")
                elif not use_job_app_gen:
                    print(f"  [jobgen] ⚠️  Skipping {company} - JobApplicationGenerator not available")
                
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
                                assets["resume"] = str(resume_path)
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
                            assets["resume"] = str(resume_path)
                            filter_stats["created"] += 1
                            print(f"  [llm] ✅ Resume saved: {resume_path.name}")
                            
                            # Generate PDF version - read from saved text file to ensure exact match
                            try:
                                from pdf_generator import generate_resume_pdf
                                pdf_path = tailored_resumes_dir / f"resume_{base}.pdf"
                                
                                # Read the exact text file content to ensure PDF matches
                                with open(resume_path, "r", encoding="utf-8") as f:
                                    exact_resume_text = f.read()
                                
                                success = generate_resume_pdf(
                                    content=exact_resume_text,  # Use exact file content
                                    output_path=str(pdf_path),
                                    job_title=role,
                                    company_name=company,
                                    candidate_name=""
                                )
                                if success:
                                    assets["resume_pdf"] = str(pdf_path)
                                    print(f"  [llm] ✅ Resume PDF saved: {pdf_path.name}")
                            except Exception as pdf_err:
                                print(f"  [llm] ⚠️  PDF generation failed: {pdf_err}")
                                import traceback
                                print(f"  [llm] Traceback: {traceback.format_exc()[:300]}")
                        
                        if cover_letter_llm:
                            txt_path = letters_dir / f"cover_{base}.txt"
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(cover_letter_llm)
                            llm_cover_generated = True
                            builder_tailored = None
                            assets["cover_letter"] = str(txt_path)
                            print(f"  [llm] ✅ Cover letter saved: {txt_path.name}")
                            
                            # Generate PDF version
                            try:
                                from pdf_generator import generate_cover_letter_pdf
                                pdf_path = letters_dir / f"cover_{base}.pdf"
                                success = generate_cover_letter_pdf(
                                    content=cover_letter_llm,
                                    output_path=str(pdf_path),
                                    job_title=role,
                                    company_name=company,
                                    candidate_name="",
                                    candidate_email="",
                                    candidate_phone=""
                                )
                                if success:
                                    assets["cover_letter_pdf"] = str(pdf_path)
                                    print(f"  [llm] ✅ Cover letter PDF saved: {pdf_path.name}")
                            except Exception as pdf_err:
                                print(f"  [llm] ⚠️  PDF generation failed: {pdf_err}")
                        
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
                            assets["resume"] = str(resume_path)
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
                                        assets["resume"] = str(resume_txt_path)
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
                            assets["resume"] = str(resume_txt_path)
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
                            assets["cover_letter"] = str(txt_path)
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
                        assets["cover_letter"] = str(txt_path)
            
            print(f"[cover] generated cover letters in {letters_dir}")
            if auto_tailor:
                print(f"[resume] generated tailored resumes in {tailored_resumes_dir}")
        except Exception as e:
            print("[cover] skipped:", e)
    autofill_cfg = resolved_cfg.get("autofill") or {}
    if autofill_cfg.get("enabled"):
        if not SELENIUM_AVAILABLE:
            print("[autofill] Selenium not available; skipping Workday autofill.")
        elif not WORKDAY_AUTOFILL_AVAILABLE:
            print("[autofill] Workday autofill module not available; skipping.")
        else:
            providers = {
                str(p).strip().lower()
                for p in (autofill_cfg.get("providers") or ["workday"])
            }
            if "workday" in providers:
                try:
                    profile = WorkdayCandidateProfile.from_mapping(
                        autofill_cfg.get("profile") or {}
                    )
                except Exception as e:
                    print(f"[autofill] {e}. Skipping Workday autofill.")
                else:
                    workday_jobs = [job for job in top if is_workday_url(job.get("url"))]
                    if not workday_jobs:
                        print("[autofill] No Workday apply links detected in top matches.")
                    else:
                        max_jobs = int(autofill_cfg.get("max_jobs", 1))
                        if max_jobs <= 0:
                            max_jobs = len(workday_jobs)
                        headless = bool(autofill_cfg.get("headless", False))
                        wait_seconds = int(autofill_cfg.get("wait_seconds", 20))
                        resume_default = (autofill_cfg.get("resume_path") or "").strip() or None
                        cover_default = (autofill_cfg.get("cover_letter_path") or "").strip() or None

                        def _asset_key(job: dict[str, Any]) -> str:
                            url = (job.get("url") or "").strip()
                            if url:
                                return url
                            raw = f"{job.get('company','')}_{job.get('title','')}"
                            return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_") or raw or "job"

                        # Daily apply budget
                        output_dir = (resolved_cfg.get("output") or {}).get("dir") or "output"
                        daily_state_path = Path(output_dir) / "autofill_daily.json"
                        today_str = datetime.utcnow().strftime("%Y-%m-%d")

                        def _load_daily_state() -> dict[str, int | str]:
                            try:
                                if daily_state_path.exists():
                                    data = json.loads(daily_state_path.read_text(encoding="utf-8"))
                                    if data.get("date") == today_str:
                                        return {"date": today_str, "used": int(data.get("used", 0))}
                            except Exception:
                                pass
                            return {"date": today_str, "used": 0}

                        def _save_daily_state(state: dict[str, int | str]) -> None:
                            try:
                                daily_state_path.parent.mkdir(parents=True, exist_ok=True)
                                daily_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
                            except Exception:
                                pass

                        daily_limit = int(autofill_cfg.get("daily_limit", 10))
                        state = _load_daily_state()
                        remaining_budget = max(0, daily_limit - int(state.get("used", 0)))
                        if remaining_budget <= 0:
                            print(f"[autofill] Daily limit reached ({daily_limit}). Skipping autofill today.")
                            # still continue to next steps (no autofill)
                            raise Exception("DAILY_LIMIT_REACHED")

                        try:
                            def _driver_factory():
                                if not create_chrome_driver:
                                    raise RuntimeError("Chrome driver factory unavailable")
                                return create_chrome_driver(headless=headless)

                            login_cfg = (autofill_cfg.get("login") or {})
                            login_user = (login_cfg.get("username") or os.getenv("WORKDAY_USERNAME") or "").strip()
                            login_pass = (login_cfg.get("password") or os.getenv("WORKDAY_PASSWORD") or "").strip()
                            create_cfg = (autofill_cfg.get("create_account") or {})
                            allow_create = bool(create_cfg.get("enabled", False))

                            with WorkdayAutofill(
                                _driver_factory,
                                profile,
                                wait_seconds=wait_seconds,
                                verbose=True,
                                login_username=login_user,
                                login_password=login_pass,
                                allow_account_creation=allow_create,
                            ) as autofiller:
                                applied = 0
                                for job in workday_jobs:
                                    if applied >= max_jobs or remaining_budget <= 0:
                                        break
                                    job_url = (job.get("url") or "").strip()
                                    if not job_url:
                                        continue
                                    key = _asset_key(job)
                                    assets = job_assets.get(job_url) or job_assets.get(key) or {}
                                    resume_path = assets.get("resume") or resume_default
                                    cover_path = assets.get("cover_letter") or cover_default
                                    if resume_path:
                                        resume_path = str(Path(resume_path).expanduser())
                                    if cover_path:
                                        cover_path = str(Path(cover_path).expanduser())
                                    print(
                                        f"[autofill] Attempting Workday autofill for "
                                        f"{job.get('company','?')} - {job.get('title','?')}"
                                    )
                                    try:
                                        autofiller.fill_application(
                                            job_url,
                                            resume_path=resume_path,
                                            cover_letter_path=cover_path,
                                        )
                                        job["autofill_status"] = "success"
                                        applied += 1
                                        # consume budget
                                        state["used"] = int(state.get("used", 0)) + 1  # type: ignore[index]
                                        remaining_budget -= 1
                                        _save_daily_state(state)
                                    except Exception as e:
                                        job["autofill_status"] = f"error: {e}"
                                        print(f"[autofill] Failed for {job_url}: {e}")
                        except Exception as e:
                            if str(e) != "DAILY_LIMIT_REACHED":
                                print(f"[autofill] Unable to start Workday automation: {e}")
                        # Greenhouse / Lever (simple) autofill
                        providers = [p.strip().lower() for p in (autofill_cfg.get("providers") or [])]
                        if PORTAL_AUTOFILL_AVAILABLE and providers:
                            try:
                                def _driver_factory2():
                                    if not create_chrome_driver:
                                        raise RuntimeError("Chrome driver factory unavailable")
                                    return create_chrome_driver(headless=headless)
                                portal_profile = PortalCandidateProfile(
                                    first_name=profile.first_name,
                                    last_name=profile.last_name,
                                    email=profile.email,
                                    phone=profile.phone,
                                )
                                gh_jobs = [j for j in top if is_greenhouse_url(j.get("url"))] if "greenhouse" in providers else []
                                lv_jobs = [j for j in top if is_lever_url(j.get("url"))] if "lever" in providers else []
                                # Apply Greenhouse
                                if gh_jobs:
                                    with SimpleGreenhouseAutofill(_driver_factory2, portal_profile, wait_seconds=wait_seconds, verbose=True) as gh:
                                        applied = 0
                                        for job in gh_jobs:
                                            if applied >= max_jobs or remaining_budget <= 0:
                                                break
                                            job_url = (job.get("url") or "").strip()
                                            if not job_url:
                                                continue
                                            key = _asset_key(job)
                                            assets = job_assets.get(job_url) or job_assets.get(key) or {}
                                            
                                            # Prefer PDF resume if available
                                            resume_path = None
                                            pdf_path_str = assets.get("resume_pdf")
                                            if pdf_path_str and Path(pdf_path_str).exists():
                                                resume_path = pdf_path_str
                                            else:
                                                resume_path = assets.get("resume") or resume_default
                                            
                                            cover_path = assets.get("cover_letter") or cover_default
                                            if resume_path:
                                                resume_path = str(Path(resume_path).expanduser())
                                            if cover_path:
                                                cover_path = str(Path(cover_path).expanduser())
                                            print(f"[autofill] Attempting Greenhouse autofill for {job.get('company','?')} - {job.get('title','?')}")
                                            try:
                                                gh.fill_application(job_url, resume_path=resume_path, cover_letter_path=cover_path)
                                                job["autofill_status"] = "success"
                                                applied += 1
                                                state["used"] = int(state.get("used", 0)) + 1  # type: ignore[index]
                                                remaining_budget -= 1
                                                _save_daily_state(state)
                                            except Exception as e:
                                                job["autofill_status"] = f"error: {e}"
                                                print(f"[autofill] Greenhouse failed for {job_url}: {e}")
                                # Apply Lever
                                if lv_jobs:
                                    with SimpleLeverAutofill(_driver_factory2, portal_profile, wait_seconds=wait_seconds, verbose=True) as lv:
                                        applied = 0
                                        for job in lv_jobs:
                                            if applied >= max_jobs or remaining_budget <= 0:
                                                break
                                            job_url = (job.get("url") or "").strip()
                                            if not job_url:
                                                continue
                                            key = _asset_key(job)
                                            assets = job_assets.get(job_url) or job_assets.get(key) or {}
                                            
                                            # Prefer PDF resume if available
                                            resume_path = None
                                            pdf_path_str = assets.get("resume_pdf")
                                            if pdf_path_str and Path(pdf_path_str).exists():
                                                resume_path = pdf_path_str
                                            else:
                                                resume_path = assets.get("resume") or resume_default
                                                
                                            cover_path = assets.get("cover_letter") or cover_default
                                            if resume_path:
                                                resume_path = str(Path(resume_path).expanduser())
                                            if cover_path:
                                                cover_path = str(Path(cover_path).expanduser())
                                            print(f"[autofill] Attempting Lever autofill for {job.get('company','?')} - {job.get('title','?')}")
                                            try:
                                                lv.fill_application(job_url, resume_path=resume_path, cover_letter_path=cover_path)
                                                job["autofill_status"] = "success"
                                                applied += 1
                                                state["used"] = int(state.get("used", 0)) + 1  # type: ignore[index]
                                                remaining_budget -= 1
                                                _save_daily_state(state)
                                            except Exception as e:
                                                job["autofill_status"] = f"error: {e}"
                                                print(f"[autofill] Lever failed for {job_url}: {e}")
                            except Exception as e:
                                print(f"[autofill] Unable to start Greenhouse/Lever automation: {e}")
    # Print filtering summary
    # Ensure summary variables exist even if earlier branches skipped filtering
    if "score_threshold" not in locals():
        try:
            score_threshold = float(resolved_cfg.get("min_score", 60))
        except Exception:
            score_threshold = 60.0
    if "filtered_jobs" not in locals():
        filtered_jobs = []
    if "tailor_threshold" not in locals():
        try:
            tailor_threshold = int(resolved_cfg.get("tailor_threshold", 40))
        except Exception:
            tailor_threshold = 40
    if "top_per_company_limit" not in locals():
        try:
            top_per_company_limit = int(resolved_cfg.get("top_per_company_limit", 1) or 1)
        except Exception:
            top_per_company_limit = 1
    if "auto_tailor" not in locals():
        auto_tailor = bool(resolved_cfg.get("auto_tailor_resume", False))
    if "use_job_app_gen" not in locals():
        use_job_app_gen = False
    if "use_llm_resumer" not in locals():
        use_llm_resumer = False
    if "company_targets" not in locals():
        company_targets = []
    if "target_roles" not in locals():
        target_roles = resolved_cfg.get("target_roles", [])
    print("\n" + "="*80)
    print("📊 JOB FILTERING & RESUME GENERATION SUMMARY")
    print("="*80)
    print(f"\n🔍 FILTERING STAGES:")
    print(f"  1️⃣  Total jobs fetched: {len(fetched)}")
    print(f"  2️⃣  After score filter (>= {score_threshold}): {len(filtered_jobs)}")
    if 'filter_stats' in locals():
        print(f"  3️⃣  Sponsorship check:")
        print(f"       - Blocked (no sponsorship): {filter_stats.get('sponsorship_blocked', 0)}")
        print(f"       - Passed sponsorship: {len(filtered_jobs) - filter_stats.get('sponsorship_blocked', 0)}")
        print(f"  4️⃣  Resumes created: {filter_stats.get('created', 0)}")
        
        # Show why resumes weren't created
        if filter_stats.get('created', 0) == 0 and len(filtered_jobs) > 0:
            print(f"\n⚠️  ISSUE: Jobs were filtered but NO RESUMES created!")
            print(f"      Possible reasons:")
            print(f"      - Jobs have no descriptions (<50 chars)")
            print(f"      - Jobs have no valid URLs")
            print(f"      - LLM generation failed")
            print(f"      - auto_tailor is False")
            print(f"\n      💡 ACTION: Check logs for [ERROR], [WARNING], or [skip] messages")
    print(f"\n⚙️  CONFIG SETTINGS:")
    print(f"  - min_score: {score_threshold}")
    print(f"  - tailor_threshold: {tailor_threshold}")
    print(f"  - top_per_company_limit: {top_per_company_limit}")
    print(f"  - auto_tailor_resume: {auto_tailor}")
    print(f"  - use_job_app_gen: {use_job_app_gen}")
    print(f"  - use_llm_resumer: {use_llm_resumer}")
    print(f"  - max possible resumes: {len(company_targets)} companies × {top_per_company_limit} = {len(company_targets) * top_per_company_limit}")
    print(f"  - companies: {len(company_targets)} ({', '.join(company_targets[:5])}...)")
    print(f"  - target_roles: {len(target_roles)} ({', '.join(target_roles[:3])}...)")
    print("="*80 + "\n")
    
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
