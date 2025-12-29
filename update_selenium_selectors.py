"""
Helper script to normalize Selenium selectors in config.json.

Usage (from repo root):
  python update_selenium_selectors.py --config config.json --apply

Without --apply it will just print a preview of suggested changes.
"""

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

from urllib.parse import urlparse


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _split_css_list(s: str) -> List[str]:
    return [p.strip() for p in (s or "").split(",") if p.strip()]


def _join_css_list(parts: List[str]) -> str:
    # Keep stable order while de-duping
    seen = set()
    out: List[str] = []
    for p in parts:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return ", ".join(out)


def _infer_require_path_contains(link_selector: str) -> str:
    """
    Generic heuristic: if link_selector contains a specific href*='/.../' fragment,
    infer require_path_contains so Selenium drops nav/PDF links.
    """
    candidates: List[str] = []
    for part in _split_css_list(link_selector):
        if "href*=" not in part:
            continue
        for quote in ("'", '"'):
            if quote not in part:
                continue
            try:
                frag = part.split("href*=")[1]
                frag = frag.split(quote)[1]
                if frag.startswith("/"):
                    candidates.append(frag)
            except Exception:
                pass
            break
    if not candidates:
        return ""
    best = max(candidates, key=len)
    # Normalize common variants
    if "/details/" in best:
        return "/details/"
    return best


def normalize_site(site: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized copy of a single selenium site entry."""
    site = copy.deepcopy(site)
    url = site.get("url") or ""
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    # Generic helpers
    def ensure_link_patterns(default_patterns: List[str]) -> str:
        existing = (site.get("link_selector") or "").strip()
        if not existing:
            return _join_css_list(default_patterns)
        # Keep existing but ensure at least one generic job URL pattern is present
        parts = _split_css_list(existing)
        for pat in default_patterns:
            if pat not in parts:
                parts.append(pat)
        return _join_css_list(parts)

    def ensure_list_patterns(default_patterns: List[str]) -> str:
        existing = (site.get("list_selector") or "").strip()
        if not existing:
            return _join_css_list(default_patterns)
        parts = _split_css_list(existing)
        for pat in default_patterns:
            if pat not in parts:
                parts.append(pat)
        return _join_css_list(parts)

    # Special cases with well-known stable patterns
    if "metacareers.com" in host:
        site["url"] = "https://www.metacareers.com/jobsearch"
        site["list_selector"] = "a[href*='/profile/job_details/']"
        site["title_selector"] = "h3"
        site["location_selector"] = "span[class*='location'], span[class*='x3a6nna'], div[class*='location']"
        site["link_selector"] = "a[href*='/profile/job_details/']"
        site["wait_selector"] = "a[href*='/profile/job_details/']"
        site.setdefault("absolute_base", "https://www.metacareers.com")
        return site

    if "uber.com" in host:
        site["list_selector"] = "a[href*='/careers/list/']"
        site["title_selector"] = "a[href*='/careers/list/'], h3, h4"
        site["location_selector"] = "span[class*='location'], div[class*='location']"
        site["link_selector"] = "a[href*='/careers/list/']"
        site["wait_selector"] = "a[href*='/careers/list/']"
        site.setdefault("absolute_base", "https://www.uber.com")
        return site

    if host.endswith("wd5.myworkdayjobs.com"):
        # Workday-powered career sites (e.g., NVIDIA, Qualcomm)
        site["list_selector"] = "li[data-automation-id='jobPosting'], div[class*='job-item']"
        site["title_selector"] = "a[data-automation-id='jobTitle'], h3"
        site["location_selector"] = "div[data-automation-id='locations']"
        site["link_selector"] = "a[data-automation-id='jobTitle']"
        site.setdefault("wait_selector", "li[data-automation-id='jobPosting']")
        return site

    # Generic fallback for "jobs" or "careers" domains
    generic_link_patterns = [
        # Common job-detail URL patterns
        "a[href*='/details/']",
        "a[href*='/en-us/details/']",
        "a[href*='/open-positions/']",
        "a[href*='requisition']",
        "a[href*='requisition-item']",
        "a[href*='jobPosting']",
        # Generic /job/ patterns
        "a[href*='/job/']",
        "a[href*='/jobs/']",
        "a[href*='careers']",
    ]
    generic_list_patterns = [
        # Common containers across career sites
        "tr[id^='job-']",
        "div.job-title.job-list-item",
        "li[data-automation-id='jobPosting']",
        "tr[data-ui='requisition-item']",
        "li[data-ui='requisition-item']",
        "div[class*='job-card']",
        "div[class*='job-listing']",
        "li[class*='job']",
        "article[class*='job']",
        "a[href*='/job/']",
        "a[href*='/jobs/']",
    ]

    site["link_selector"] = ensure_link_patterns(generic_link_patterns)
    site["list_selector"] = ensure_list_patterns(generic_list_patterns)

    # Be conservative with title/location: keep existing if present
    if not site.get("title_selector"):
        site["title_selector"] = "a[class*='job-title'], h2, h3, a[href*='/job/'], a[href*='/jobs/']"
    if not site.get("location_selector"):
        site["location_selector"] = "span[class*='location'], div[class*='location']"

    if not site.get("wait_selector"):
        site["wait_selector"] = site["list_selector"]

    # Generic guardrail: if link_selector suggests a specific path fragment,
    # enforce it at URL level to reduce nav/PDF links being treated as jobs.
    if not site.get("require_path_contains"):
        inferred = _infer_require_path_contains(site.get("link_selector") or "")
        if inferred:
            site["require_path_contains"] = inferred

    # Fill missing domain/base values (don't overwrite user-provided values)
    if not site.get("domain_filter") and host:
        site["domain_filter"] = host
    if not site.get("absolute_base") and host:
        scheme = parsed.scheme or "https"
        site["absolute_base"] = f"{scheme}://{host}"

    return site


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Selenium selectors in config.json")
    parser.add_argument("--config", type=str, default="config.json", help="Path to config JSON")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes in-place to the config file (otherwise just preview).",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        raise SystemExit(f"Config file not found: {cfg_path}")

    data = load_config(cfg_path)
    selenium_opts = data.get("selenium_options", {}) or {}
    sites = selenium_opts.get("sites") or []
    if not isinstance(sites, list) or not sites:
        raise SystemExit("No selenium_options.sites found in config.")

    updated_sites: List[Dict[str, Any]] = []
    print("Normalizing Selenium selectors for the following sites:\n")
    for site in sites:
        if not isinstance(site, dict):
            updated_sites.append(site)
            continue
        company = site.get("company") or "<unknown>"
        url = site.get("url") or ""
        new_site = normalize_site(site)
        updated_sites.append(new_site)

        if site != new_site:
            print(f"- {company}:")
            print(f"  url: {url}")
            if site.get("list_selector") != new_site.get("list_selector"):
                print(f"    list_selector: {site.get('list_selector')}  ->  {new_site.get('list_selector')}")
            if site.get("title_selector") != new_site.get("title_selector"):
                print(f"    title_selector: {site.get('title_selector')}  ->  {new_site.get('title_selector')}")
            if site.get("location_selector") != new_site.get("location_selector"):
                print(f"    location_selector: {site.get('location_selector')}  ->  {new_site.get('location_selector')}")
            if site.get("link_selector") != new_site.get("link_selector"):
                print(f"    link_selector: {site.get('link_selector')}  ->  {new_site.get('link_selector')}")
            if site.get("wait_selector") != new_site.get("wait_selector"):
                print(f"    wait_selector: {site.get('wait_selector')}  ->  {new_site.get('wait_selector')}")
            print("")

    data["selenium_options"]["sites"] = updated_sites

    if args.apply:
        save_config(cfg_path, data)
        print(f"\n✅ Applied selector normalization to {cfg_path}")
    else:
        print("\n(Preview only – no changes written. Re-run with --apply to save changes.)")


if __name__ == "__main__":
    main()


