"""
Daily pipeline entry point for Lever/Greenhouse applications.

This script:
1. Loads the shared configuration JSON.
2. Uses the hosted board fetchers to pull jobs from Lever / Greenhouse.
3. Runs the JobApplicationAgent directly on the fetched job list so the
   tailored resumes / cover letters are generated and saved.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from job_application_agent import create_agent_from_config, JobApplicationAgent
from match import fetch_company_source_jobs


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_jobs(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    company_sources = config.get("company_sources") or {}
    fetch_limit = int(config.get("fetch_limit", 200))
    # Prefer explicit greenhouse country if provided, else top-level country
    gh_country = (
        (company_sources.get("greenhouse") or {}).get("country")
        or config.get("country")
    )
    return fetch_company_source_jobs(company_sources, fetch_limit, gh_country)


def run_pipeline(config_path: Path) -> Dict[str, Any]:
    config_dict = load_config(config_path)
    agent: JobApplicationAgent = create_agent_from_config(str(config_path))

    jobs = build_jobs(config_dict)
    print(f"[pipeline] fetched {len(jobs)} jobs from Lever/Greenhouse APIs")
    agent.stats["jobs_discovered"] = len(jobs)

    applications = agent.analyze_jobs(jobs)
    agent.applications = applications

    top_matches = [
        app for app in applications if app.score >= agent.config.min_match_score
    ][: agent.config.max_jobs_to_apply]

    print(f"[pipeline] processing {len(top_matches)} top matches...")

    for idx, app in enumerate(top_matches, start=1):
        print(f"[pipeline] #{idx}: {app.company} - {app.title} ({app.score:.1f})")

        if len(app.description) < 100:
            agent.enrich_job_description(app)

        if agent.config.auto_generate_resume or agent.config.auto_generate_cover_letter:
            if agent.generate_application_materials(app):
                agent.save_application(app)

    agent.stats["applications_submitted"] = 0  # Auto-submit not yet implemented
    return {
        **agent.stats,
        "applications": [app.to_dict() for app in top_matches],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply to Lever/Greenhouse jobs")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to configuration JSON (default: config.json)",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    stats = run_pipeline(config_path)
    print("[pipeline] stats:", json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

