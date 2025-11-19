"""
Daily pipeline entry point for Greenhouse applications.

This script:
1. Loads the shared configuration JSON.
2. Uses the hosted board fetchers to pull jobs from Greenhouse.
3. Runs the JobApplicationAgent directly on the fetched job list so the
   tailored resumes / cover letters are generated and saved.
4. Uses Selenium to autofill the applications on Greenhouse.
5. Handles Workday account creation and login using environment variables.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from job_application_agent import create_agent_from_config, JobApplicationAgent
from match import fetch_company_source_jobs
# Imports for autofill
from portal_autofill import SimpleGreenhouseAutofill, CandidateProfile
from workday_autofill import WorkdayAutofill, is_workday_url
from selenium_scraper import create_chrome_driver


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
    print(f"[pipeline] fetched {len(jobs)} jobs from Greenhouse API")
    agent.stats["jobs_discovered"] = len(jobs)

    applications = agent.analyze_jobs(jobs)
    agent.applications = applications

    top_matches = [
        app for app in applications if app.score >= agent.config.min_match_score
    ][: agent.config.max_jobs_to_apply]

    print(f"[pipeline] processing {len(top_matches)} top matches...")

    # Setup Autofill
    autofill_cfg = config_dict.get("autofill", {})
    do_autofill = autofill_cfg.get("enabled", False)
    
    gh_autofill = None
    wd_autofill = None
    
    prof_data = autofill_cfg.get("profile", {})
    profile = CandidateProfile(
        first_name=prof_data.get("first_name", ""),
        last_name=prof_data.get("last_name", ""),
        email=prof_data.get("email", ""),
        phone=prof_data.get("phone", "")
    )
    
    # Use headless setting from config
    headless = autofill_cfg.get("headless", False)
    driver_factory = lambda: create_chrome_driver(headless=headless)
    
    if do_autofill:
        if "greenhouse" in autofill_cfg.get("providers", []):
            print("[pipeline] Autofill enabled for Greenhouse")
            gh_autofill = SimpleGreenhouseAutofill(driver_factory, profile, verbose=True)
            gh_autofill.__enter__()
        
        if "workday" in autofill_cfg.get("providers", []):
            print("[pipeline] Autofill enabled for Workday")
            wd_username = os.getenv("WORKDAY_EMAIL")
            wd_password = os.getenv("WORKDAY_PASSWORD")
            if wd_username and wd_password:
                wd_autofill = WorkdayAutofill(
                    driver_factory, 
                    profile, 
                    verbose=True,
                    login_username=wd_username,
                    login_password=wd_password,
                    allow_account_creation=True
                )
                wd_autofill.__enter__()
            else:
                 print("[pipeline] Workday credentials (WORKDAY_EMAIL, WORKDAY_PASSWORD) missing in env variables.")

    try:
        for idx, app in enumerate(top_matches, start=1):
            print(f"[pipeline] #{idx}: {app.company} - {app.title} ({app.score:.1f})")

            if len(app.description) < 100:
                agent.enrich_job_description(app)

            generated = False
            if agent.config.auto_generate_resume or agent.config.auto_generate_cover_letter:
                if agent.generate_application_materials(app):
                    agent.save_application(app)
                    generated = True
            
            # Apply if generated and autofill is active
            if generated and do_autofill:
                # Determine paths (logic mirrors agent.save_application)
                output_dir = Path(agent.config.output_dir)
                safe_company = "".join(c if c.isalnum() else "_" for c in app.company)
                
                # Try PDF first
                safe_title = "".join(c if c.isalnum() else "_" for c in (app.title or "resume"))
                pdf_path = output_dir / "tailored_resumes" / f"{safe_company}_{safe_title}.pdf"
                
                resume_path = None
                if pdf_path.exists():
                    resume_path = str(pdf_path)
                else:
                    # Fallback to TXT
                    txt_path = output_dir / safe_company / f"resume_{safe_company}.txt"
                    if txt_path.exists():
                        resume_path = str(txt_path)
                
                cover_path = None
                txt_cover = output_dir / safe_company / f"cover_letter_{safe_company}.txt"
                if txt_cover.exists():
                    cover_path = str(txt_cover)
                
                if resume_path:
                    try:
                        # Greenhouse
                        if gh_autofill and "greenhouse" in (app.url or "").lower():
                             print(f"[pipeline] Autofilling Greenhouse application for {app.company}...")
                             gh_autofill.fill_application(app.url, resume_path, cover_path)
                             agent.stats["applications_submitted"] += 1
                             app.status = "submitted"
                             app.submitted_at = "now"
                        
                        # Workday
                        elif wd_autofill and is_workday_url(app.url):
                             print(f"[pipeline] Autofilling Workday application for {app.company}...")
                             wd_autofill.fill_application(app.url, resume_path, cover_path)
                             agent.stats["applications_submitted"] += 1
                             app.status = "submitted"
                             app.submitted_at = "now"

                    except Exception as e:
                        print(f"[pipeline] Autofill failed: {e}")
                        agent.stats["failures"] += 1
                else:
                     print(f"[pipeline] Skipping autofill - no resume file found")

    finally:
        if gh_autofill:
            gh_autofill.close()
        if wd_autofill:
            wd_autofill.close()

    return {
        **agent.stats,
        "applications": [app.to_dict() for app in top_matches],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply to Greenhouse jobs")
    parser.add_argument(
        "--config",
        default="config.greenhouse.json",
        help="Path to configuration JSON (default: config.greenhouse.json)",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    stats = run_pipeline(config_path)
    print("[pipeline] stats:", json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
