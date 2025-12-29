"""
LLM-powered Selenium site configuration generator.

Given a list of company names, this module prompts an LLM to suggest the
primary job/careers listing URLs and returns ready-to-use metadata entries
compatible with the selenium scraper configuration.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

try:
    import openai_compat  # noqa: F401
except Exception:
    openai_compat = None

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False


MODEL_NAME = os.getenv("LLM_SITES_MODEL", "gpt-4o-mini")

PROMPT_TEMPLATE = """
You are an expert in identifying official job listing pages for companies.

For EACH company listed below, produce an object describing its primary careers
site suitable for a Selenium scraper. Provide best-effort CSS selectors that
identify individual job listings, title elements, and locations on the page.
When unsure, fall back to generic selectors that commonly work on career pages.

COMPANY LIST:
{company_list}

Respond with ONLY valid JSON in the following format (array of objects):
[
  {{
    "company": "company-slug",
    "url": "https://jobs.example.com/search",
    "careers_url": "https://www.example.com/careers/",
    "list_selector": "CSS selector matching listing containers",
    "title_selector": "CSS selector for the job title element",
    "location_selector": "CSS selector for location text",
    "link_selector": "CSS selector for link to job detail"
  }},
  ...
]

Rules:
- company should be lowercase slug (spaces replaced by hyphen).
- url should point directly to a listing/search page if possible.
- careers_url should be the generic careers landing page.
- All selectors must be CSS selectors using double quotes.
- Do NOT include comments or Markdown. JSON only.
"""


DEFAULT_SELECTORS = {
    "list_selector": "a[href*='/job'], a[href*='/jobs/'], li[class*='job'], div[class*='job']",
    "title_selector": "h2, h3, a[href*='/job']",
    "location_selector": "span[class*='location'], div[class*='location']",
    "link_selector": "a[href*='/job'], a[href*='/jobs/']",
    "wait_selector": "a[href*='/job'], a[href*='/jobs/']",
}


def _clean_json_string(text: str) -> str:
    """Remove fenced code blocks or trailing text from an LLM response."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, count=1).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    return stripped


def _standardize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in defaults and ensure required fields are present."""
    company = (entry.get("company") or "").strip().lower()
    company_slug = re.sub(r"[^a-z0-9\-]+", "-", company).strip("-") or company

    url = (entry.get("url") or entry.get("job_search_url") or entry.get("jobs_url") or "").strip()
    careers_url = (entry.get("careers_url") or url or "").strip()

    parsed = urlparse(url or careers_url)
    domain = parsed.netloc
    absolute_base = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""

    standardized = {
        "company": company_slug,
        "url": url or careers_url,
        "careers_url": careers_url or (absolute_base if absolute_base else url),
        "list_selector": entry.get("list_selector") or DEFAULT_SELECTORS["list_selector"],
        "title_selector": entry.get("title_selector") or DEFAULT_SELECTORS["title_selector"],
        "location_selector": entry.get("location_selector") or DEFAULT_SELECTORS["location_selector"],
        "link_selector": entry.get("link_selector") or DEFAULT_SELECTORS["link_selector"],
        "wait_selector": entry.get("wait_selector") or DEFAULT_SELECTORS["wait_selector"],
        "sleep_seconds": entry.get("sleep_seconds") or 3,
        "source": entry.get("source") or f"selenium:{company_slug}",
        "domain_filter": entry.get("domain_filter") or domain,
        "absolute_base": entry.get("absolute_base") or absolute_base,
    }
    return standardized


def generate_selenium_site_entries(companies: List[str]) -> List[Dict[str, Any]]:
    """Generate Selenium site configuration objects for the given companies."""
    companies = [c.strip() for c in companies if c and c.strip()]
    if not companies:
        return []

    # Check config.json to see if OpenAI is enabled
    openai_enabled_in_config = True
    try:
        config_path = Path(__file__).parent / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                openai_cfg = config.get("openai") or {}
                openai_enabled_in_config = bool(openai_cfg.get("enabled", True))
    except Exception:
        pass  # If config read fails, fall back to checking environment variables

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    # If OpenAI is disabled in config, skip it entirely
    if not openai_enabled_in_config and provider == "openai":
        if gemini_key:
            provider = "gemini"
            print("[llm-selenium] OpenAI disabled in config, using Gemini")
        else:
            print("[llm-selenium] OpenAI disabled and no Gemini key, skipping site generation")
            return []
    
    if provider == "openai" and not openai_key:
        if gemini_key:
            provider = "gemini"
            print("[llm-selenium] OpenAI key missing, falling back to Gemini")
        else:
            print("[llm-selenium] No LLM API keys found, skipping site generation")
            return []
            
    prompt = PROMPT_TEMPLATE.format(company_list="\n".join(f"- {c}" for c in companies))
    raw_text = ""
    
    if provider == "openai":
        try:
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You generate structured JSON for Selenium job scrapers."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            print(f"[llm-selenium] OpenAI request failed: {exc}")
            return []
    elif provider == "gemini":
        if not GEMINI_AVAILABLE:
            print("[llm-selenium] Gemini library not available")
            return []
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            raw_text = response.text or ""
        except Exception as exc:
            print(f"[llm-selenium] Gemini request failed: {exc}")
            return []
    else:
        print(f"[llm-selenium] Unsupported provider: {provider}")
        return []

    if not raw_text:
        print("[llm-selenium] Empty response content for site generation.")
        return []

    cleansed = _clean_json_string(raw_text)
    try:
        parsed = json.loads(cleansed)
    except json.JSONDecodeError as exc:
        print(f"[llm-selenium] Failed to parse JSON from LLM: {exc}\nRaw:\n{cleansed}")
        return []

    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        print("[llm-selenium] Unexpected JSON structure from LLM (expected list).")
        return []

    standardized_entries = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        standardized_entries.append(_standardize_entry(entry))

    return standardized_entries

