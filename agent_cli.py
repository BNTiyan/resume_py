#!/usr/bin/env python3
"""
CLI for running the Job Application Agent with automatic submissions.
"""
import argparse
import json
import os
from pathlib import Path
from job_application_agent import JobApplicationAgent, AgentConfig
# Import autofill classes
from portal_autofill import SimpleGreenhouseAutofill, CandidateProfile, is_greenhouse_url, is_lever_url, SimpleLeverAutofill
from workday_autofill import WorkdayAutofill, is_workday_url
from selenium_scraper import create_chrome_driver

def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Job Application Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent_cli.py
  python agent_cli.py --config my_config.json
  python agent_cli.py --dry-run
        """
    )
    
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )
    parser.add_argument(
        "--companies",
        nargs="+",
        help="Target companies to search"
    )
    parser.add_argument(
        "--roles",
        nargs="+",
        help="Target roles to search for"
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        help="Maximum jobs to apply to"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        help="Minimum match score (0-100)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually submit applications"
    )
    parser.add_argument(
        "--auto-submit",
        action="store_true",
        default=True,
        help="Automatically submit applications"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for generated materials"
    )
    
    args = parser.parse_args()
    
    # Load base config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return 1
    
    with open(config_path, 'r') as f:
        config_dict = json.load(f)
    
    # Build agent configuration
    agent_config = AgentConfig(
        resume_path=config_dict.get("resume", "input/resume.yml"),
        candidate_name=config_dict.get("cover_letter", {}).get("name", "Candidate"),
        target_roles=args.roles or config_dict.get("companies", ["software engineer"]),
        target_companies=args.companies or config_dict.get("companies", []),
        max_jobs_to_fetch=config_dict.get("fetch_limit", 500),
        max_jobs_to_apply=args.max_jobs or config_dict.get("top", 15),
        min_match_score=args.min_score or 60.0,
        auto_generate_resume=config_dict.get("auto_tailor_resume", True),
        auto_generate_cover_letter=True,
        auto_submit=args.auto_submit or config_dict.get("autofill", {}).get("enabled", False),
        dry_run=args.dry_run,
        output_dir=args.output_dir or config_dict.get("output", {}).get("dir", "output"),
        verbose=True
    )
    
    # Build job sources from config
    sources = []
    selenium_sites = config_dict.get("selenium_options", {}).get("sites", [])
    for site in selenium_sites:
        if isinstance(site, dict) and site.get("url"):
            sources.append(site)
        elif isinstance(site, str):
            sources.append({"url": site})
    
    if not sources and agent_config.target_companies:
         print("No selenium sites found, using default list logic...")
         # ... (fallback logic if needed, omitted for brevity as config usually has sites)

    if not sources:
        print("Error: No job sources configured. Add 'selenium_options.sites' to config.json")
        return 1
    
    print(f"\nJob Application Agent")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Target companies: {', '.join(agent_config.target_companies) if agent_config.target_companies else 'Any'}")
    print(f"  Auto-submit: {agent_config.auto_submit} (dry_run={agent_config.dry_run})")
    print("=" * 60)
    
    if agent_config.auto_submit and not agent_config.dry_run:
        # Check for Workday credentials if needed
        if not os.getenv("WORKDAY_EMAIL") or not os.getenv("WORKDAY_PASSWORD"):
            print("Warning: WORKDAY_EMAIL and WORKDAY_PASSWORD env vars are not set.")
            print("Workday autofill will fail if attempted.")

    # Create agent
    agent = JobApplicationAgent(agent_config)
    
    # Run discovery and analysis
    try:
        print(f"Discovering jobs from {len(sources)} sources...")
        jobs = agent.discover_jobs(sources)
        agent.applications = agent.analyze_jobs(jobs)
        
        top_matches = [
            app for app in agent.applications 
            if app.score >= agent.config.min_match_score
        ][:agent.config.max_jobs_to_apply]
        
        print(f"Processing top {len(top_matches)} matches...")

        # Setup Autofill Drivers
        # Initialize autofill drivers only if auto-submit is on and not dry-run
        gh_autofill = None
        wd_autofill = None
        lv_autofill = None
        
        if agent_config.auto_submit and not agent_config.dry_run:
            autofill_cfg = config_dict.get("autofill", {})
            prof_data = autofill_cfg.get("profile", {})
            profile = CandidateProfile(
                first_name=prof_data.get("first_name", ""),
                last_name=prof_data.get("last_name", ""),
                email=prof_data.get("email", ""),
                phone=prof_data.get("phone", "")
            )
            headless = autofill_cfg.get("headless", False)
            driver_factory = lambda: create_chrome_driver(headless=headless)
            
            # Initialize providers based on need or config
            # We'll initialize lazily or globally. Globally is safer for session reuse.
            providers = autofill_cfg.get("providers", [])
            
            if "greenhouse" in providers:
                gh_autofill = SimpleGreenhouseAutofill(driver_factory, profile, verbose=True)
                gh_autofill.__enter__()
            
            if "lever" in providers:
                lv_autofill = SimpleLeverAutofill(driver_factory, profile, verbose=True)
                lv_autofill.__enter__()

            if "workday" in providers:
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

        # Process each job
        for idx, app in enumerate(top_matches):
            print(f"[{idx+1}/{len(top_matches)}] {app.company} - {app.title} (Score: {app.score:.1f})")
            
            # Enrich
            if len(app.description) < 100:
                agent.enrich_job_description(app)
            
            # Generate
            generated = False
            if agent.config.auto_generate_resume or agent.config.auto_generate_cover_letter:
                if agent.generate_application_materials(app):
                    agent.save_application(app)
                    generated = True
            
            # Submit
            if generated and agent_config.auto_submit and not agent_config.dry_run:
                # Locate files
                output_dir = Path(agent.config.output_dir)
                safe_company = "".join(c if c.isalnum() else "_" for c in app.company)
                safe_title = "".join(c if c.isalnum() else "_" for c in (app.title or "resume"))
                
                # Resume path (prefer PDF)
                pdf_path = output_dir / "tailored_resumes" / f"{safe_company}_{safe_title}.pdf"
                resume_path = str(pdf_path) if pdf_path.exists() else None
                if not resume_path:
                     txt_path = output_dir / safe_company / f"resume_{safe_company}.txt"
                     if txt_path.exists():
                         resume_path = str(txt_path)
                
                # Cover letter path
                cover_path = None
                txt_cover = output_dir / safe_company / f"cover_letter_{safe_company}.txt"
                if txt_cover.exists():
                    cover_path = str(txt_cover)
                
                if resume_path:
                    try:
                        submitted = False
                        url_lower = (app.url or "").lower()
                        
                        # Routing logic
                        if gh_autofill and is_greenhouse_url(app.url):
                            print(f"  Autofilling Greenhouse: {app.url}")
                            gh_autofill.fill_application(app.url, resume_path, cover_path)
                            submitted = True
                        elif lv_autofill and is_lever_url(app.url):
                            print(f"  Autofilling Lever: {app.url}")
                            lv_autofill.fill_application(app.url, resume_path, cover_path)
                            submitted = True
                        elif wd_autofill and is_workday_url(app.url):
                            print(f"  Autofilling Workday: {app.url}")
                            wd_autofill.fill_application(app.url, resume_path, cover_path)
                            submitted = True
                        
                        if submitted:
                            agent.stats["applications_submitted"] += 1
                            app.status = "submitted"
                            app.submitted_at = "now"
                        else:
                            print(f"  No matching autofiller for URL: {app.url}")
                            
                    except Exception as e:
                        print(f"  Autofill failed: {e}")
                        agent.stats["failures"] += 1
                else:
                    print("  Skipping autofill - no resume file found")

        # Cleanup drivers
        if gh_autofill: gh_autofill.close()
        if wd_autofill: wd_autofill.close()
        if lv_autofill: lv_autofill.close()

        # Save final stats
        results = {
            **agent.stats,
            "elapsed_seconds": 0, # Calculate properly if needed
            "applications": [app.to_dict() for app in top_matches]
        }
        results_path = Path(agent_config.output_dir) / "agent_results.json"
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {results_path}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as e:
        print(f"\nAgent failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
