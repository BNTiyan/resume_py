#!/usr/bin/env python3
"""
Quick Apply Tool - Generate Resume, Cover Letter, and Match Score from Job Link or Description

Usage:
    python3 quick_apply.py --job-link "https://example.com/job"
    python3 quick_apply.py --job-description "Job description text here"
    python3 quick_apply.py --jd-file "path/to/job_description.txt"
"""

import argparse
import sys
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import requests
from bs4 import BeautifulSoup
import re

# Import existing modules
from match import (
    fetch_job_description_from_url,
    score_job,
    load_resume_data
)
from enhanced_prompts import ENHANCED_RESUME_PROMPT, ENHANCED_COVER_LETTER_PROMPT
from pdf_generator import PDFGenerator
from docx_generator import WordDocumentGenerator
from llm_manager import LLMManager
from cover_letter import CoverLetterBuilder


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json"""
    config_path = Path("config.json")
    if not config_path.exists():
        print("❌ config.json not found!")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return json.load(f)


def extract_job_info_from_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract company name and job title from URL"""
    company = None
    title = None
    
    # Try to extract from common job board patterns
    url_lower = url.lower()
    
    # Greenhouse pattern
    if 'greenhouse.io' in url_lower or 'boards.greenhouse.io' in url_lower:
        match = re.search(r'boards\.greenhouse\.io/([^/]+)', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
    
    # Lever pattern
    elif 'lever.co' in url_lower or 'jobs.lever.co' in url_lower:
        match = re.search(r'jobs\.lever\.co/([^/]+)', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
    
    # LinkedIn pattern
    elif 'linkedin.com/jobs' in url_lower:
        match = re.search(r'currentJobId=(\d+)', url)
        if match:
            company = "LinkedIn Job"
    
    # Google Careers
    elif 'careers.google.com' in url_lower:
        company = "Google"
    
    # General pattern - try to extract from domain
    else:
        match = re.search(r'https?://(?:www\.|careers\.)?([^/\.]+)', url)
        if match:
            company = match.group(1).title()
    
    return company, title


def fetch_job_description(job_link: Optional[str] = None, 
                         job_description: Optional[str] = None,
                         jd_file: Optional[str] = None) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Fetch job description from link, text, or file
    Returns: (description, company_name, job_title)
    """
    company_name = None
    job_title = None
    
    if job_link:
        print(f"🔍 Fetching job description from: {job_link}")
        description = fetch_job_description_from_url(job_link)
        if not description:
            print("❌ Failed to fetch job description from URL")
            sys.exit(1)
        
        # Try to extract company and title from URL
        company_name, job_title = extract_job_info_from_url(job_link)
        
        # Try to extract from the description itself
        soup = BeautifulSoup(description, 'html.parser')
        text = soup.get_text()
        
        # Look for company name patterns
        if not company_name:
            company_match = re.search(r'(?:Company|Organization|About)\s*[:]\s*([A-Z][A-Za-z\s&]+?)(?:\n|\.)', text)
            if company_match:
                company_name = company_match.group(1).strip()
        
        # Look for job title patterns
        if not job_title:
            title_match = re.search(r'(?:Position|Role|Title|Job Title)\s*[:]\s*([A-Z][A-Za-z\s/\-&]+?)(?:\n|\.)', text)
            if title_match:
                job_title = title_match.group(1).strip()
        
        print(f"✅ Fetched {len(description)} characters")
        return description, company_name, job_title
    
    elif job_description:
        print("📝 Using provided job description")
        return job_description, company_name, job_title
    
    elif jd_file:
        print(f"📄 Reading job description from: {jd_file}")
        jd_path = Path(jd_file)
        if not jd_path.exists():
            print(f"❌ File not found: {jd_file}")
            sys.exit(1)
        
        with open(jd_path, 'r', encoding='utf-8') as f:
            description = f.read()
        
        print(f"✅ Loaded {len(description)} characters")
        return description, company_name, job_title
    
    else:
        print("❌ No job source provided")
        sys.exit(1)


def prompt_for_missing_info(company_name: Optional[str], job_title: Optional[str]) -> Tuple[str, str]:
    """Prompt user for company name and job title if not auto-detected"""
    if not company_name:
        company_name = input("📝 Enter company name: ").strip()
        if not company_name:
            company_name = "Company"
    
    if not job_title:
        job_title = input("📝 Enter job title: ").strip()
        if not job_title:
            job_title = "Position"
    
    return company_name, job_title


def generate_resume_and_cover_letter(
    job_description: str,
    company_name: str,
    job_title: str,
    resume_data: Dict[str, Any],
    config: Dict[str, Any],
    output_dir: Path
) -> Tuple[str, str, str]:
    """
    Generate tailored resume and cover letter
    Returns: (resume_path, cover_letter_path, resume_text)
    """
    print("\n🤖 Generating tailored resume and cover letter...")
    
    # Initialize LLM Manager
    llm_manager = LLMManager(config)
    
    # Convert resume data to text
    from resume_utils import render_resume_from_yaml
    resume_text = render_resume_from_yaml(resume_data)
    
    # Generate resume using LLM
    resume_prompt = ENHANCED_RESUME_PROMPT.format(
        company_name=company_name,
        job_title=job_title,
        job_description=job_description,
        resume_text=resume_text
    )
    
    print("  📄 Generating resume content...")
    tailored_resume = None
    try:
        tailored_resume = llm_manager.generate(resume_prompt, max_tokens=6000)
    except Exception as e:
        print(f"  ⚠️ LLM resume generation failed: {e}")
    
    if not tailored_resume:
        # Fallback: use base resume text if LLM is unavailable
        print("  ⚠️ Falling back to base resume text (no LLM tailoring).")
        tailored_resume = resume_text
    
    # Generate cover letter using LLM, with deterministic fallback
    cover_letter_prompt = ENHANCED_COVER_LETTER_PROMPT.format(
        company_name=company_name,
        job_title=job_title,
        job_description=job_description,
        resume_text=resume_text
    )
    
    print("  💌 Generating cover letter content...")
    cover_letter = None
    try:
        cover_letter = llm_manager.generate(cover_letter_prompt, max_tokens=1500)
    except Exception as e:
        print(f"  ⚠️ LLM cover letter generation failed: {e}")
    
    if not cover_letter:
        # Deterministic, non-LLM fallback: reuse existing CoverLetterBuilder logic
        print("  💌 Falling back to deterministic cover letter builder...")
        candidate_name = resume_data.get("basics", {}).get("name", "")
        builder = CoverLetterBuilder(resume_text, candidate_name)
        cover_letter = builder.compose_concise_text(job_description, company_name, job_title)
    
    if not cover_letter:
        print("❌ Failed to generate cover letter (LLM + fallback)")
        sys.exit(1)
    
    # Generate PDF and DOCX files
    pdf_gen = PDFGenerator()
    docx_gen = WordDocumentGenerator()
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize filenames
    safe_company = re.sub(r'[^\w\s-]', '', company_name)[:30]
    safe_title = re.sub(r'[^\w\s-]', '', job_title)[:30]
    base_name = f"{safe_company}_{safe_title}".replace(' ', '_')
    
    # Generate resume files
    resume_pdf_path = output_dir / f"{base_name}_resume.pdf"
    resume_docx_path = output_dir / f"{base_name}_resume.docx"
    
    print("  📑 Generating resume PDF...")
    pdf_gen.generate_resume_pdf(
        tailored_resume,
        str(resume_pdf_path),
        job_title=job_title,
        company_name=company_name,
        candidate_name=resume_data.get("basics", {}).get("name", ""),
        structured=resume_data
    )
    
    print("  📑 Generating resume DOCX...")
    docx_gen.generate_resume_docx(
        tailored_resume,
        str(resume_docx_path),
        job_title=job_title,
        company_name=company_name,
        candidate_name=resume_data.get("basics", {}).get("name", ""),
        structured=resume_data
    )
    
    # Generate cover letter files
    cover_letter_pdf_path = output_dir / f"{base_name}_cover_letter.pdf"
    cover_letter_docx_path = output_dir / f"{base_name}_cover_letter.docx"
    
    print("  💌 Generating cover letter PDF...")
    basics = resume_data.get("basics", {}) or {}
    candidate_name = basics.get("name", "")
    candidate_email = basics.get("email", "")
    candidate_phone = basics.get("phone", "")

    pdf_gen.generate_cover_letter_pdf(
        cover_letter,
        str(cover_letter_pdf_path),
        job_title=job_title,
        company_name=company_name,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone,
    )
    
    print("  💌 Generating cover letter DOCX...")
    docx_gen.generate_cover_letter_docx(
        cover_letter,
        str(cover_letter_docx_path),
        job_title=job_title,
        company_name=company_name,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone,
    )
    
    return str(resume_pdf_path), str(cover_letter_pdf_path), tailored_resume


def calculate_match_score(resume_text: str, job_description: str, company_name: str, job_title: str) -> float:
    """Calculate match score between resume and job description"""
    print("\n📊 Calculating match score...")
    
    # Create job dict for score_job function
    job_dict = {
        'title': job_title,
        'company': company_name,
        'location': '',
        'description': job_description
    }
    score = score_job(job_dict, resume_text)
    
    return score


def print_summary(
    company_name: str,
    job_title: str,
    match_score: float,
    resume_path: str,
    cover_letter_path: str
):
    """Print summary of generated documents"""
    print("\n" + "="*70)
    print("✅ SUCCESS! Documents Generated")
    print("="*70)
    print(f"\n📌 Job Details:")
    print(f"   Company: {company_name}")
    print(f"   Position: {job_title}")
    print(f"\n📊 Match Score: {match_score:.1f}%")
    
    # Color-coded match score
    if match_score >= 70:
        print("   🟢 Excellent Match!")
    elif match_score >= 50:
        print("   🟡 Good Match")
    else:
        print("   🟠 Moderate Match")
    
    print(f"\n📄 Generated Files:")
    print(f"   Resume (PDF):  {resume_path}")
    print(f"   Resume (DOCX): {resume_path.replace('.pdf', '.docx')}")
    print(f"   Cover Letter (PDF):  {cover_letter_path}")
    print(f"   Cover Letter (DOCX): {cover_letter_path.replace('.pdf', '.docx')}")
    print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Quick Apply Tool - Generate tailored resume and cover letter from job link or description",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From job link
  python3 quick_apply.py --job-link "https://boards.greenhouse.io/company/jobs/12345"
  
  # From job description text
  python3 quick_apply.py --job-description "Software Engineer position at Company X..."
  
  # From job description file
  python3 quick_apply.py --jd-file "job_description.txt"
  
  # Specify company and title manually
  python3 quick_apply.py --job-link "..." --company "Google" --title "ML Engineer"
  
  # Custom output directory
  python3 quick_apply.py --job-link "..." --output "my_applications"
        """
    )
    
    # Job source (one required)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        '--job-link', '--url',
        help='Job posting URL (Greenhouse, Lever, LinkedIn, etc.)'
    )
    source_group.add_argument(
        '--job-description', '--jd',
        help='Job description text (inline)'
    )
    source_group.add_argument(
        '--jd-file', '--file',
        help='Path to file containing job description'
    )
    
    # Optional overrides
    parser.add_argument(
        '--company', '-c',
        help='Company name (auto-detected if not provided)'
    )
    parser.add_argument(
        '--title', '-t',
        help='Job title (auto-detected if not provided)'
    )
    parser.add_argument(
        '--output', '-o',
        default='output/quick_apply',
        help='Output directory (default: output/quick_apply)'
    )
    parser.add_argument(
        '--resume', '-r',
        default='input/resume.yml',
        help='Path to resume YAML file (default: input/resume.yml)'
    )
    parser.add_argument(
        '--no-prompt',
        action='store_true',
        help='Do not prompt for missing information (use defaults)'
    )
    
    args = parser.parse_args()
    
    print("🚀 Quick Apply Tool - Resume & Cover Letter Generator")
    print("="*70)
    
    # Load configuration
    config = load_config()
    
    # Load resume data
    print(f"\n📋 Loading resume from: {args.resume}")
    resume_path = Path(args.resume)
    if not resume_path.exists():
        print(f"❌ Resume file not found: {args.resume}")
        sys.exit(1)
    
    resume_text, resume_data = load_resume_data(resume_path)
    if not resume_data:
        print("❌ Failed to load resume data")
        sys.exit(1)
    
    print(f"✅ Resume loaded")
    
    # Fetch job description
    job_description, company_name, job_title = fetch_job_description(
        job_link=args.job_link,
        job_description=args.job_description,
        jd_file=args.jd_file
    )
    
    # Override with command-line arguments if provided
    if args.company:
        company_name = args.company
    if args.title:
        job_title = args.title
    
    # Prompt for missing info if not in no-prompt mode
    if not args.no_prompt:
        company_name, job_title = prompt_for_missing_info(company_name, job_title)
    else:
        if not company_name:
            company_name = "Company"
        if not job_title:
            job_title = "Position"
    
    print(f"\n🎯 Target Position:")
    print(f"   Company: {company_name}")
    print(f"   Title: {job_title}")
    
    # Generate resume and cover letter
    output_dir = Path(args.output)
    resume_path, cover_letter_path, tailored_resume = generate_resume_and_cover_letter(
        job_description=job_description,
        company_name=company_name,
        job_title=job_title,
        resume_data=resume_data,
        config=config,
        output_dir=output_dir
    )
    
    # Calculate match score
    match_score = calculate_match_score(tailored_resume, job_description, company_name, job_title)
    
    # Print summary
    print_summary(
        company_name=company_name,
        job_title=job_title,
        match_score=match_score,
        resume_path=resume_path,
        cover_letter_path=cover_letter_path
    )


if __name__ == "__main__":
    main()

