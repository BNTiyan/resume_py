import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from match import (
    load_selenium_sites_from_opts,  # reuse normalization helper
    enrich_jobs_with_descriptions,
    score_job,
)
from selenium_scraper import fetch_selenium_sites, SELENIUM_AVAILABLE
from resume_utils import load_resume_data


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch job links (company, title, location, URL) using Selenium sites from "
            "config.json and compute a fuzzy match score against your resume text."
        )
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to config JSON (default: config.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output/job_links.json",
        help="Path to write job links JSON (default: output/job_links.json)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of jobs to fetch across all sites (default: 200)",
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    cfg = load_config(config_path)
    selenium_opts = cfg.get("selenium_options", {}) or {}

    # Load resume text used for scoring
    resume_path = Path(cfg.get("resume", "input/resume.yml"))
    if not resume_path.exists():
        raise SystemExit(f"Resume file not found: {resume_path}")

    resume_text, resume_struct = load_resume_data(resume_path)
    if not resume_text.strip():
        raise SystemExit(f"Resume text is empty from: {resume_path}")

    if not SELENIUM_AVAILABLE:
        raise SystemExit("Selenium is not available; install selenium + webdriver-manager to use this script.")

    sites = load_selenium_sites_from_opts(selenium_opts)
    if not sites:
        raise SystemExit("No Selenium sites configured in config.json (selenium_options.sites).")

    fetch_limit = int(cfg.get("fetch_limit", args.limit) or args.limit)

    print(f"Fetching job links from {len(sites)} sites (limit={fetch_limit})...")
    raw_jobs: List[Dict[str, Any]] = fetch_selenium_sites(sites, fetch_limit=fetch_limit)

    # Optionally enrich jobs with full descriptions based on JD keywords/skills
    target_roles = cfg.get("target_roles", []) or []
    resume_lower = resume_text.lower()
    resume_skills: set[str] = set()
    common_skills = {
        "python", "java", "javascript", "typescript", "c++", "go", "rust", "scala",
        "react", "angular", "vue", "node", "django", "flask", "spring",
        "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
        "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
        "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "kafka", "spark", "airflow", "mlflow", "kubeflow",
        "machine learning", "deep learning", "nlp", "computer vision", "mlops",
    }
    for skill in common_skills:
        if skill in resume_lower:
            resume_skills.add(skill)

    if target_roles or resume_skills:
        print(f"[links] Enriching {len(raw_jobs)} jobs with descriptions for better scoring...")
        raw_jobs = enrich_jobs_with_descriptions(
            raw_jobs,
            target_roles,
            resume_skills,
            max_workers=int(cfg.get("parallel_workers", 5)) or 5,
        )

    # Normalize to a minimal link record + score and deduplicate by URL
    links_by_url: Dict[str, Dict[str, Any]] = {}
    for job in raw_jobs or []:
        url = job.get("url") or job.get("link")
        if not url:
            continue
        url = str(url).strip()
        if not url:
            continue
        score = score_job(job, resume_text)
        record = {
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "location": job.get("location", ""),
            "url": url,
            "source": job.get("source", ""),
            "score": round(float(score), 2),
        }
        links_by_url[url] = record

    links: List[Dict[str, Any]] = list(links_by_url.values())

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(links, f, indent=2)

    # Also write a CSV next to the JSON for easy viewing/filtering
    csv_path = output_path.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        # Columns: job role (title), company, location, URL, score, source
        writer.writerow(["title", "company", "location", "url", "score", "source"])
        for row in links:
            writer.writerow([
                row.get("title", ""),
                row.get("company", ""),
                row.get("location", ""),
                row.get("url", ""),
                row.get("score", ""),
                row.get("source", ""),
            ])

    print(f"Wrote {len(links)} unique job links to {output_path} and {csv_path}")


if __name__ == "__main__":
    main()


