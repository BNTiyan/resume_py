from __future__ import annotations
"""
Intelligent Job Application Agent

An autonomous agent that:
1. Discovers job opportunities from multiple sources
2. Analyzes and scores jobs based on your profile
3. Extracts detailed job descriptions using LLMs
4. Generates tailored resumes and cover letters
5. Optionally submits applications automatically

This agent orchestrates all components and can run continuously or on-demand.
"""
import os
import json
import time
import csv
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import logging
try:
    from job_application_generator import JobApplicationGenerator  # top-level import
except Exception:
    JobApplicationGenerator = None  # type: ignore[misc]

from resume_utils import load_resume_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("execution.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("JobAgent")


@dataclass
class AgentConfig:
    """Configuration for the Job Application Agent"""
    # Resume and profile
    resume_path: str
    candidate_name: str
    target_roles: List[str]
    target_companies: List[str] = None
    target_locations: List[str] = None
    
    # Job search settings
    max_jobs_to_fetch: int = 500
    max_jobs_to_apply: int = 10
    min_match_score: float = 60.0
    
    # LLM settings
    openai_api_key: str = None
    openai_model: str = "gpt-4o-mini"
    use_embeddings: bool = True
    
    # Generation settings
    auto_generate_resume: bool = True
    auto_generate_cover_letter: bool = True
    
    # Submission settings
    auto_submit: bool = False
    submit_providers: List[str] = None  # e.g., ["workday", "greenhouse"]
    
    # Output settings
    output_dir: str = "output"
    save_applications: bool = True
    
    # Agent behavior
    dry_run: bool = True  # Don't actually submit applications
    verbose: bool = True
    max_retries: int = 3
    retry_delay: int = 5
    
    def __post_init__(self):
        if self.openai_api_key is None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.submit_providers is None:
            self.submit_providers = ["workday"]
        if self.target_companies is None:
            self.target_companies = []
        if self.target_locations is None:
            self.target_locations = []


@dataclass
class JobApplication:
    """Represents a complete job application"""
    job_id: str
    company: str
    title: str
    location: str
    url: str
    score: float
    description: str
    
    # Generated assets
    tailored_resume: Optional[str] = None
    cover_letter: Optional[str] = None
    
    # Metadata
    discovered_at: str = None
    generated_at: Optional[str] = None
    submitted_at: Optional[str] = None
    status: str = "discovered"  # discovered, generated, submitted, failed
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class JobApplicationAgent:
    """
    Autonomous agent for job discovery, analysis, and application.
    """
    
    def __init__(self, config: AgentConfig):
        """
        Initialize the agent with configuration.
        
        Args:
            config: AgentConfig instance with all settings
        """
        self.config = config
        self.applications: List[JobApplication] = []
        self.stats = {
            "jobs_discovered": 0,
            "jobs_analyzed": 0,
            "jobs_above_threshold": 0,
            "resumes_generated": 0,
            "cover_letters_generated": 0,
            "applications_submitted": 0,
            "failures": 0
        }
        self.llm_disabled_reason: Optional[str] = None
        self.gemini_fallback_attempted = False
        self.base_resume_text: str = ""
        self.resume_structured: Optional[Dict[str, Any]] = None
        
        # Initialize components
        self._init_components()
        
        logger.info("Job Application Agent initialized")
        logger.info(f"  Target roles: {', '.join(config.target_roles)}")
        logger.info(f"  Target companies: {', '.join(config.target_companies) if config.target_companies else 'Any'}")
        logger.info(f"  Auto-submit: {config.auto_submit} (dry_run={config.dry_run})")
    
    def _init_components(self):
        """Initialize all required components"""
        try:
            from intelligent_job_scraper import IntelligentJobScraper
            from llm_job_description_extractor import JobDescriptionExtractor
            from selenium_scraper import create_chrome_driver
            
            resume_path = Path(self.config.resume_path).expanduser()
            if not resume_path.exists():
                raise FileNotFoundError(f"Resume file not found: {resume_path}")
            self.base_resume_text, self.resume_structured = load_resume_data(resume_path)
            if self.config.candidate_name == "Candidate" and self.resume_structured:
                basics = self.resume_structured.get("basics") or {}
                candidate = basics.get("name") or ""
                if candidate:
                    self.config.candidate_name = candidate
            
            self.scraper = IntelligentJobScraper(
                driver_factory=lambda: create_chrome_driver(headless=True),
                verbose=self.config.verbose
            )
            self.job_desc_extractor = None
            self.app_generator = None

            if self.config.openai_api_key:
                self.job_desc_extractor = JobDescriptionExtractor(self.config.openai_api_key)
                self.app_generator = self._build_application_generator("openai")
                if self.app_generator:
                    logger.info("LLM components initialized (OpenAI)")
                else:
                    logger.warning("Failed to initialize OpenAI application generator")
            else:
                logger.warning("No OpenAI API key - LLM features disabled")
            
            # Optionally initialize autofill
            if self.config.auto_submit:
                try:
                    from workday_autofill import WorkdayAutofill
                    self.autofill_available = True
                    logger.info("Autofill components available")
                except Exception:
                    self.autofill_available = False
                    logger.warning("Autofill not available")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    def discover_jobs(self, sources: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Discover jobs from multiple sources.
        
        Args:
            sources: List of source configurations (URLs, companies, etc.)
            
        Returns:
            List of discovered jobs
        """
        logger.info(f"Discovering jobs from {len(sources)} sources...")
        all_jobs = []
        
        for idx, source in enumerate(sources):
            try:
                logger.info(f"  [{idx+1}/{len(sources)}] Scraping {source.get('company', source.get('url', 'unknown'))}")
                
                if "url" in source:
                    jobs = self.scraper.scrape_jobs(
                        url=source["url"],
                        company=source.get("company", ""),
                        max_jobs=self.config.max_jobs_to_fetch // len(sources),
                        wait_seconds=5
                    )
                    all_jobs.extend(jobs)
                    logger.info(f"    Found {len(jobs)} jobs")
                
            except Exception as e:
                logger.error(f"  Failed to scrape {source}: {e}")
                self.stats["failures"] += 1
                continue
        
        self.stats["jobs_discovered"] = len(all_jobs)
        logger.info(f"Total jobs discovered: {len(all_jobs)}")
        return all_jobs
    
    def score_job(self, job: Dict[str, Any]) -> float:
        """
        Score a job based on match with profile.
        
        Args:
            job: Job dictionary
            
        Returns:
            Match score (0-100)
        """
        score = 0.0
        
        # Title matching
        title_lower = job.get("title", "").lower()
        for target_role in self.config.target_roles:
            if target_role.lower() in title_lower:
                score += 40.0
                break
        
        # Company matching
        if self.config.target_companies:
            company_lower = job.get("company", "").lower()
            for target_company in self.config.target_companies:
                if target_company.lower() in company_lower:
                    score += 30.0
                    break
        else:
            score += 20.0  # No preference, give some points
        
        # Location matching
        if self.config.target_locations:
            location_lower = job.get("location", "").lower()
            for target_loc in self.config.target_locations:
                if target_loc.lower() in location_lower:
                    score += 20.0
                    break
        else:
            score += 10.0
        
        # Has URL
        if job.get("url"):
            score += 10.0
        
        return min(score, 100.0)
    
    def analyze_jobs(self, jobs: List[Dict[str, Any]]) -> List[JobApplication]:
        """
        Analyze and score jobs, creating JobApplication objects.
        
        Args:
            jobs: List of raw job dictionaries
            
        Returns:
            List of JobApplication objects, sorted by score
        """
        logger.info(f"Analyzing {len(jobs)} jobs...")
        applications = []
        
        for idx, job in enumerate(jobs):
            try:
                score = self.score_job(job)
                
                app = JobApplication(
                    job_id=job.get("url") or f"{job.get('company')}_{job.get('title')}_{idx}",
                    company=job.get("company", "Unknown"),
                    title=job.get("title", "Unknown"),
                    location=job.get("location", "Unknown"),
                    url=job.get("url", ""),
                    score=score,
                    description=job.get("description", "")
                )
                
                applications.append(app)
                
            except Exception as e:
                logger.error(f"  Error analyzing job {idx}: {e}")
                continue
        
        # Sort by score
        applications.sort(key=lambda x: x.score, reverse=True)
        
        self.stats["jobs_analyzed"] = len(applications)
        above_threshold = [a for a in applications if a.score >= self.config.min_match_score]
        self.stats["jobs_above_threshold"] = len(above_threshold)
        
        logger.info(f"Analysis complete: {len(above_threshold)} jobs above threshold ({self.config.min_match_score})")
        
        return applications
    
    def enrich_job_description(self, application: JobApplication) -> bool:
        """
        Enrich job description using LLM extraction.
        
        Args:
            application: JobApplication to enrich
            
        Returns:
            True if successful
        """
        if not self.job_desc_extractor:
            return False
        
        try:
            if not application.description or len(application.description) < 100:
                if application.url:
                    logger.info(f"  [LLM] Enriching job description for {application.company}...")
                    import requests
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    }
                    resp = requests.get(application.url, timeout=30, headers=headers)
                    resp.raise_for_status()
                    
                    extracted = self.job_desc_extractor.extract_job_description(
                        resp.text,
                        application.company,
                        application.title
                    )
                    
                    if extracted and extracted.get("description"):
                        # Build comprehensive description
                        desc_parts = []
                        for key in ["description", "responsibilities", "minimum_qualifications", "preferred_qualifications"]:
                            if extracted.get(key):
                                desc_parts.append(extracted[key])
                        
                        application.description = "\n\n".join(desc_parts)
                        logger.info(f"  [LLM] Enriched description: {len(application.description)} chars")
                        return True
            
            return len(application.description) > 100
            
        except Exception as e:
            logger.error(f"  [LLM] Enrichment failed: {e}")
            return False
    
    def generate_application_materials(self, application: JobApplication) -> bool:
        """
        Generate tailored resume and cover letter.
        
        Args:
            application: JobApplication to generate materials for
            
        Returns:
            True if successful
        """
        if not self.app_generator:
            logger.warning("  No LLM available for generation - falling back to base resume")
            if self.base_resume_text:
                application.tailored_resume = self.base_resume_text
                application.generated_at = datetime.now().isoformat()
                application.status = "generated"
                self.stats["resumes_generated"] += 1
                return True
            return False

        if self.llm_disabled_reason:
            logger.warning("  LLM generation skipped for %s (reason: %s)", application.company, self.llm_disabled_reason)
            if self.base_resume_text:
                logger.info("  Falling back to base resume due to LLM disabled")
                application.tailored_resume = self.base_resume_text
                application.generated_at = datetime.now().isoformat()
                application.status = "generated"
                self.stats["resumes_generated"] += 1
                return True
            return False
        
        try:
            logger.info(f"  [LLM] Generating application materials for {application.company}...")
            
            result = self.app_generator.generate_application_package(
                application.description,
                application.company,
                application.title,
                parallel=True
            )
            
            if result.get("resume"):
                application.tailored_resume = result["resume"]
                self.stats["resumes_generated"] += 1
                logger.info(f"  [LLM] Generated tailored resume")
            
            if result.get("cover_letter"):
                application.cover_letter = result["cover_letter"]
                self.stats["cover_letters_generated"] += 1
                logger.info(f"  [LLM] Generated cover letter")
            
            application.generated_at = datetime.now().isoformat()
            application.status = "generated"
            
            return bool(result.get("resume") or result.get("cover_letter"))
            
        except Exception as e:
            logger.error(f"  [LLM] Generation failed: {e}")
            msg = str(e).lower()
            if "insufficient_quota" in msg or "exceeded your current quota" in msg:
                gemini_key = os.getenv("GEMINI_API_KEY")
                if gemini_key and not self.gemini_fallback_attempted:
                    logger.warning("  OpenAI quota exceeded. Attempting Gemini fallback...")
                    self.gemini_fallback_attempted = True
                    try:
                        self.app_generator = self._build_application_generator("gemini")
                        if self.app_generator:
                            self.llm_disabled_reason = None
                            return self.generate_application_materials(application)
                    except Exception as gemini_exc:
                        logger.error("  Gemini fallback initialization failed: %s", gemini_exc)
                # Final fallback to base resume if available
                if self.base_resume_text:
                    logger.warning("  Falling back to base resume due to LLM failure")
                    application.tailored_resume = self.base_resume_text
                    application.generated_at = datetime.now().isoformat()
                    application.status = "generated"
                    self.stats["resumes_generated"] += 1
                    return True
                self.llm_disabled_reason = "insufficient_quota"
                logger.error("  Disabling LLM generation for remainder of run due to insufficient quota.")
            application.error = str(e)
            application.status = "failed"
            self.stats["failures"] += 1
            return False
    
    def save_application(self, application: JobApplication) -> None:
        """Save application materials to disk"""
        if not self.config.save_applications:
            return
        
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create company subdirectory
        safe_company = "".join(c if c.isalnum() else "_" for c in application.company)
        company_dir = output_dir / safe_company
        company_dir.mkdir(exist_ok=True)
        
        # Save resume
        if application.tailored_resume:
            resume_path = company_dir / f"resume_{safe_company}.txt"
            with open(resume_path, "w", encoding="utf-8") as f:
                f.write(application.tailored_resume)
            
            # Also generate a PDF version of the resume for convenience
            try:
                # Lazy import to avoid hard dependency if reportlab isn't installed
                from pdf_generator import generate_resume_pdf  # type: ignore
                tailored_dir = output_dir / "tailored_resumes"
                tailored_dir.mkdir(exist_ok=True)
                # Build a safe filename with company and title
                safe_title = "".join(c if c.isalnum() else "_" for c in (application.title or "resume"))
                pdf_path = tailored_dir / f"{safe_company}_{safe_title}.pdf"
                generate_resume_pdf(
                    application.tailored_resume,
                    str(pdf_path),
                    job_title=application.title,
                    company_name=application.company,
                    candidate_name=self.config.candidate_name,
                    structured=self.resume_structured,
                )
            except Exception as e:
                logger.warning("  Could not generate PDF resume: %s", e)
        
        # Save cover letter
        if application.cover_letter:
            cover_path = company_dir / f"cover_letter_{safe_company}.txt"
            with open(cover_path, "w", encoding="utf-8") as f:
                f.write(application.cover_letter)
        
        # Save combined TXT (metadata + resume + cover letter)
        combined_lines = []
        combined_lines.append(f"Company: {application.company}")
        combined_lines.append(f"Title: {application.title}")
        combined_lines.append(f"Location: {application.location}")
        combined_lines.append(f"URL: {application.url}")
        combined_lines.append(f"Score: {application.score:.1f}")
        combined_lines.append(f"Generated At: {application.generated_at or ''}")
        combined_lines.append("")
        if application.tailored_resume:
            combined_lines.append("===== Tailored Resume =====")
            combined_lines.append(application.tailored_resume)
            combined_lines.append("")
        if application.cover_letter:
            combined_lines.append("===== Cover Letter =====")
            combined_lines.append(application.cover_letter)
            combined_lines.append("")
        combined_text = "\n".join(combined_lines).strip() + "\n"
        combined_path = company_dir / f"application_{safe_company}.txt"
        with open(combined_path, "w", encoding="utf-8") as f:
            f.write(combined_text)
        
        # Also append to a run-level combined file for convenience
        all_combined_path = output_dir / "applications_combined.txt"
        with open(all_combined_path, "a", encoding="utf-8") as f:
            f.write(f"{'=' * 80}\n")
            f.write(combined_text)
        
        # Save metadata
        metadata_path = company_dir / f"metadata_{safe_company}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(application.to_dict(), f, indent=2)
        
        # Track application in CSV
        self._append_to_applications_csv(application, output_dir, company_dir, safe_company)
        
        logger.info(f"  Saved application materials to {company_dir}")
    
    def _append_to_applications_csv(
        self, 
        application: JobApplication, 
        output_dir: Path, 
        company_dir: Path,
        safe_company: str
    ) -> None:
        """
        Append application details to a CSV file for easy tracking.
        
        CSV includes: Company, Title, Location, Job URL, Score, Status,
        Resume Path, Cover Letter Path, Generated At, Submitted At
        """
        csv_path = output_dir / "applications_tracker.csv"
        
        # Determine file paths
        safe_title = "".join(c if c.isalnum() else "_" for c in (application.title or "resume"))
        
        # Resume path (prefer PDF, fallback to TXT)
        pdf_path = output_dir / "tailored_resumes" / f"{safe_company}_{safe_title}.pdf"
        resume_path = str(pdf_path.relative_to(output_dir)) if pdf_path.exists() else ""
        if not resume_path:
            txt_path = company_dir / f"resume_{safe_company}.txt"
            if txt_path.exists():
                resume_path = str(txt_path.relative_to(output_dir))
        
        # Cover letter path
        cover_letter_path = ""
        cover_txt = company_dir / f"cover_letter_{safe_company}.txt"
        if cover_txt.exists():
            cover_letter_path = str(cover_txt.relative_to(output_dir))
        
        # Prepare CSV row
        row_data = {
            'Company': application.company,
            'Title': application.title,
            'Location': application.location,
            'Job URL': application.url,
            'Score': f"{application.score:.2f}",
            'Status': application.status,
            'Resume Path': resume_path,
            'Cover Letter Path': cover_letter_path,
            'Generated At': application.generated_at or '',
            'Submitted At': application.submitted_at or '',
            'Discovered At': application.discovered_at or '',
            'Error': application.error or ''
        }
        
        # Write header if file doesn't exist
        file_exists = csv_path.exists()
        
        with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Company', 'Title', 'Location', 'Job URL', 'Score', 'Status',
                'Resume Path', 'Cover Letter Path', 'Generated At', 'Submitted At',
                'Discovered At', 'Error'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(row_data)
        
        logger.debug(f"  Appended to applications_tracker.csv")
    
    def run(self, sources: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Run the complete agent workflow.
        
        Args:
            sources: List of job sources to search
            
        Returns:
            Statistics dictionary
        """
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("JOB APPLICATION AGENT STARTING")
        logger.info("=" * 60)
        
        try:
            # Step 1: Discover jobs
            jobs = self.discover_jobs(sources)
            
            # Step 2: Analyze and score
            self.applications = self.analyze_jobs(jobs)
            
            # Step 3: Process top matches
            top_matches = [
                app for app in self.applications 
                if app.score >= self.config.min_match_score
            ][:self.config.max_jobs_to_apply]
            
            logger.info(f"Processing top {len(top_matches)} matches...")
            
            for idx, app in enumerate(top_matches):
                logger.info(f"[{idx+1}/{len(top_matches)}] {app.company} - {app.title} (Score: {app.score:.1f})")
                
                # Enrich description if needed
                if len(app.description) < 100:
                    self.enrich_job_description(app)
                
                # Generate materials
                if self.config.auto_generate_resume or self.config.auto_generate_cover_letter:
                    success = self.generate_application_materials(app)
                    
                    if success:
                        self.save_application(app)
                    
                    # Rate limiting
                    time.sleep(2)
            
            # Step 4: Submit applications (if enabled)
            if self.config.auto_submit and not self.config.dry_run:
                logger.info("Auto-submit enabled - submitting applications...")
                # TODO: Implement submission logic
                pass
            
            elapsed = time.time() - start_time
            logger.info("=" * 60)
            logger.info("AGENT RUN COMPLETE")
            logger.info(f"  Time elapsed: {elapsed:.1f}s")
            logger.info(f"  Jobs discovered: {self.stats['jobs_discovered']}")
            logger.info(f"  Jobs above threshold: {self.stats['jobs_above_threshold']}")
            logger.info(f"  Resumes generated: {self.stats['resumes_generated']}")
            logger.info(f"  Cover letters generated: {self.stats['cover_letters_generated']}")
            logger.info(f"  Applications submitted: {self.stats['applications_submitted']}")
            logger.info(f"  Failures: {self.stats['failures']}")
            logger.info("=" * 60)
            
            return {
                **self.stats,
                "elapsed_seconds": elapsed,
                "applications": [app.to_dict() for app in top_matches]
            }
            
        except Exception as e:
            logger.error(f"Agent run failed: {e}")
            raise

    def _build_application_generator(self, provider: str) -> Optional[JobApplicationGenerator]:
        if JobApplicationGenerator is None:
            logger.error("JobApplicationGenerator is unavailable (import failed).")
            return None
        try:
            api_key = None
            if provider == "openai":
                api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
            elif provider == "gemini":
                api_key = os.getenv("GEMINI_API_KEY")
            generator = JobApplicationGenerator(api_key=api_key, provider=provider)
            generator.set_resume(self.base_resume_text)
            if provider == "gemini":
                logger.info("Gemini fallback initialized successfully")
            return generator
        except Exception as exc:
            logger.error("  Failed to initialize %s application generator: %s", provider, exc)
            return None


def create_agent_from_config(config_path: str) -> JobApplicationAgent:
    """
    Create an agent from a JSON configuration file.
    
    Args:
        config_path: Path to config.json
        
    Returns:
        Configured JobApplicationAgent
    """
    with open(config_path, 'r') as f:
        config_dict = json.load(f)
    
    # Allow configurable threshold and locations
    min_score = config_dict.get("min_match_score", config_dict.get("score_threshold", 60.0))
    target_locations = config_dict.get("target_locations") or config_dict.get("locations") or []

    agent_config = AgentConfig(
        resume_path=config_dict.get("resume", "input/resume.yml"),
        candidate_name=config_dict.get("cover_letter", {}).get("name", "Candidate"),
        target_roles=config_dict.get("target_roles", ["software engineer"]),
        target_companies=config_dict.get("companies", []),
        target_locations=target_locations,
        max_jobs_to_fetch=config_dict.get("fetch_limit", 500),
        max_jobs_to_apply=config_dict.get("top", 15),
        min_match_score=float(min_score),
        auto_generate_resume=config_dict.get("auto_tailor_resume", True),
        auto_generate_cover_letter=True,
        auto_submit=config_dict.get("autofill", {}).get("enabled", False),
        output_dir=config_dict.get("output", {}).get("dir", "output"),
        verbose=True
    )
    
    return JobApplicationAgent(agent_config)

