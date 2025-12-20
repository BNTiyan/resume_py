#!/usr/bin/env python3
"""
Quick Apply Web App - Flask Backend
Generate tailored resume and cover letter through a web interface
"""

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import json
from pathlib import Path
import tempfile
import shutil
from datetime import datetime
import traceback

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
from resume_utils import render_resume_from_yaml
from resume_parser import parse_resume_file
import re
from docx import Document as DocxDocument
from PyPDF2 import PdfReader

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'output/web_uploads'
app.config['OUTPUT_FOLDER'] = 'output/web_output'

# Ensure directories exist
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
Path(app.config['OUTPUT_FOLDER']).mkdir(parents=True, exist_ok=True)


def load_config():
    """Load configuration from config.json"""
    config_path = Path("config.json")
    if not config_path.exists():
        return None
    with open(config_path, 'r') as f:
        return json.load(f)


def extract_job_info_from_url(url: str):
    """Extract company name and job title from URL"""
    company = None
    title = None
    
    url_lower = url.lower()
    
    # Greenhouse
    if 'greenhouse.io' in url_lower:
        match = re.search(r'boards\.greenhouse\.io/([^/]+)', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
    
    # Lever
    elif 'lever.co' in url_lower:
        match = re.search(r'jobs\.lever\.co/([^/]+)', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
    
    # Google
    elif 'careers.google.com' in url_lower:
        company = "Google"
    
    # General domain extraction
    else:
        match = re.search(r'https?://(?:www\.|careers\.)?([^/\.]+)', url)
        if match:
            company = match.group(1).title()
    
    return company, title


def get_overlapping_skills(resume_data, job_description: str) -> list[str]:
    """Return a list of candidate skills that appear in the job description."""
    if not resume_data or not job_description:
        return []

    jd_lower = job_description.lower()

    overlaps: list[str] = []
    seen: set[str] = set()

    for group in resume_data.get("skills", []) or []:
        for kw in group.get("keywords", []) or []:
            skill = str(kw).strip()
            if not skill:
                continue
            key = skill.lower()
            if key in seen:
                continue
            if key in jd_lower:
                overlaps.append(skill)
                seen.add(key)

    return overlaps


def build_relevant_skills_section(resume_data, job_description: str) -> str:
    """
    Heuristic, non-LLM booster:
    - Find overlap between your YAML skills and the job description.
    - Add a short 'Relevant Skills for This Role' section that paraphrases
      those overlaps so the text is closer to the JD and boosts score_job.
    """
    overlaps = get_overlapping_skills(resume_data, job_description)
    if not overlaps:
        return ""

    # Limit to a reasonable number to keep section compact
    overlaps = overlaps[:12]

    lines: list[str] = []
    lines.append("RELEVANT SKILLS FOR THIS ROLE")
    lines.append("")
    lines.append("The following skills from my background align directly with this position:")

    # Group skills into small clusters and paraphrase slightly
    chunk_size = 4
    for i in range(0, len(overlaps), chunk_size):
        chunk = overlaps[i : i + chunk_size]
        if not chunk:
            continue
        if len(chunk) == 1:
            skills_phrase = chunk[0]
        elif len(chunk) == 2:
            skills_phrase = f"{chunk[0]} and {chunk[1]}"
        else:
            skills_phrase = ", ".join(chunk[:-1]) + f", and {chunk[-1]}"

        lines.append(f"- Hands-on experience with {skills_phrase}, which is explicitly called out in the job description.")

    lines.append("- Proven track record applying these skills in production environments, as detailed in the work experience above.")

    return "\n".join(lines).strip()


def build_fallback_cover_letter(resume_data, job_title: str, company_name: str, job_description: str) -> str:
    """
    Non-LLM cover letter template with 2–3 relevant paragraphs.
    Uses:
    - basics.summary from YAML
    - overlapping skills between resume and JD
    """
    basics = resume_data.get("basics", {}) or {}
    name = basics.get("name", "")
    summary_list = basics.get("summary", []) or []

    overlaps = get_overlapping_skills(resume_data, job_description)
    top_skills = overlaps[:4]

    paragraphs: list[str] = []

    # Paragraph 1: interest + role/company
    p1 = f"I am very interested in the {job_title} role at {company_name} and believe my background is a strong match for your needs."
    paragraphs.append(p1)

    # Paragraph 2: core profile from summary
    if summary_list:
        core_points = " ".join(summary_list[:2])
        p2 = (
            "Over my recent roles, I have focused on building reliable, production-ready systems. "
            f"{core_points}"
        )
        paragraphs.append(p2)

    # Paragraph 3: explicit alignment with JD skills
    if top_skills:
        if len(top_skills) == 1:
            skills_phrase = top_skills[0]
        elif len(top_skills) == 2:
            skills_phrase = f"{top_skills[0]} and {top_skills[1]}"
        else:
            skills_phrase = ", ".join(top_skills[:-1]) + f", and {top_skills[-1]}"

        p3 = (
            f"For this position, I bring hands-on experience with {skills_phrase}, "
            "which directly aligns with the technologies and responsibilities highlighted in the job description. "
            "I have applied these skills in real projects to deliver measurable impact and improve engineering workflows."
        )
        paragraphs.append(p3)

    # Final paragraph: closing
    closing = (
        "Thank you for your time and consideration. I would welcome the opportunity to discuss how my background "
        "can help your team deliver high-quality, scalable solutions."
    )
    paragraphs.append(closing)

    body = "\n\n".join(paragraphs)

    header = "Dear Hiring Manager,"
    footer = f"Sincerely,\n{name}" if name else "Sincerely,\n"

    return f"{header}\n\n{body}\n\n{footer}"


def build_score_explanation(
    resume_data,
    job_description: str,
    match_score: float,
    overlapping_skills: list[str],
) -> str:
    """
    Generate a short, human-readable explanation of why the score looks the way it does.
    This is heuristic and non-LLM, similar to ATS tools that give a brief rationale.
    """
    basics = resume_data.get("basics", {}) or {}
    label = basics.get("label", "") or basics.get("title", "")

    # Overall band
    if match_score >= 85:
        overall_phrase = "Your resume shows a very strong alignment with this role"
    elif match_score >= 70:
        overall_phrase = "Your resume demonstrates a strong match for this role"
    elif match_score >= 50:
        overall_phrase = "Your resume is a moderate match for this role"
    else:
        overall_phrase = "Your resume currently has a weaker match for this role"

    # Skills highlight
    skills_phrase = ""
    if overlapping_skills:
        top = overlapping_skills[:4]
        if len(top) == 1:
            s = top[0]
        elif len(top) == 2:
            s = f"{top[0]} and {top[1]}"
        else:
            s = ", ".join(top[:-1]) + f", and {top[-1]}"
        skills_phrase = f" by emphasizing key skills such as {s}"

    # Simple guidance
    if match_score >= 80:
        guidance = " You can push this even higher by adding a few more role-specific keywords and concrete impact metrics from the job description."
    elif match_score >= 60:
        guidance = " To strengthen the match, consider adding more of the job's specific tools, domains, and outcome-focused bullet points into your experience and skills sections."
    else:
        guidance = " To improve this score, you may need to add missing core skills from the job description and expand relevant experience bullets that directly mirror the role's responsibilities."

    extra = ""
    if label:
        extra = f" Your profile as a {label} is reflected in the summary and experience sections, which helps the ATS understand your seniority level."

    return overall_phrase + skills_phrase + "." + extra + guidance


def extract_text_from_resume_file(file_path: Path) -> str:
    """Extract plain text from an uploaded resume (PDF or DOCX)."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        try:
            reader = PdfReader(str(file_path))
            texts = []
            for page in reader.pages:
                try:
                    texts.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n".join(texts).strip()
        except Exception as e:
            print(f"[upload] Failed to extract text from PDF: {e}")
            return ""
    elif suffix in (".docx",):
        try:
            doc = DocxDocument(str(file_path))
            return "\n".join([p.text for p in doc.paragraphs]).strip()
        except Exception as e:
            print(f"[upload] Failed to extract text from DOCX: {e}")
            return ""
    else:
        print(f"[upload] Unsupported resume file type: {suffix}")
        return ""


def generate_documents(
    job_description,
    company_name,
    job_title,
    resume_data,
    config,
    base_resume_text: str | None = None,
    basics_override: dict | None = None,
):
    """Generate resume and cover letter"""
    try:
        # Convert resume to text (base content). If a user-uploaded resume
        # was provided, prefer that text as the base; otherwise use YAML.
        if base_resume_text and base_resume_text.strip():
            resume_text = base_resume_text.strip()
        else:
            resume_text = render_resume_from_yaml(resume_data)

        tailored_resume = None
        cover_letter = None

        # Try to use LLM if available
        try:
            llm_manager = LLMManager(config)

            # Generate resume with LLM
            resume_prompt = ENHANCED_RESUME_PROMPT.format(
                company_name=company_name,
                job_title=job_title,
                job_description=job_description,
                resume_text=resume_text,
            )
            tailored_resume = llm_manager.generate(resume_prompt, max_tokens=6000)

            # Generate cover letter with LLM
            cover_letter_prompt = ENHANCED_COVER_LETTER_PROMPT.format(
                company_name=company_name,
                job_title=job_title,
                job_description=job_description,
                resume_text=resume_text,
            )
            cover_letter = llm_manager.generate(cover_letter_prompt, max_tokens=1500)
        except Exception as llm_error:
            # LLM completely unavailable (no keys, quotas, etc.) – fall back.
            # IMPORTANT: Do NOT change `resume_text` here. We keep whichever
            # base we already had:
            # - If the user uploaded a resume, we keep that uploaded text.
            # - If not, we keep the YAML-based resume text.
            # This way, the user always gets a full resume even when the LLM is
            # out of quota or misconfigured.
            print(f"⚠️ LLM unavailable, falling back to base resume only: {llm_error}")

        # If LLM failed, at least use the base resume text and a simple cover letter template
        if not tailored_resume:
            tailored_resume = resume_text

        if not cover_letter:
            cover_letter = build_fallback_cover_letter(
                resume_data=resume_data,
                job_title=job_title,
                company_name=company_name,
                job_description=job_description,
            )
        # Heuristic, non-LLM booster: append a "Relevant Skills" section based
        # on overlaps between your YAML skills and the job description.
        overlaps_for_section = get_overlapping_skills(resume_data, job_description)
        relevant_section = build_relevant_skills_section(resume_data, job_description)
        if relevant_section:
            enhanced_resume = tailored_resume.rstrip() + "\n\n" + relevant_section
        else:
            enhanced_resume = tailored_resume

        # Generate files
        pdf_gen = PDFGenerator()
        docx_gen = WordDocumentGenerator()
        
        # Create unique output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company = re.sub(r'[^\w\s-]', '', company_name)[:30]
        safe_title = re.sub(r'[^\w\s-]', '', job_title)[:30]
        output_dir = Path(app.config['OUTPUT_FOLDER']) / f"{timestamp}_{safe_company}_{safe_title}".replace(' ', '_')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate files
        base_name = f"{safe_company}_{safe_title}".replace(' ', '_')
        
        resume_pdf = output_dir / f"{base_name}_resume.pdf"
        resume_docx = output_dir / f"{base_name}_resume.docx"
        cover_pdf = output_dir / f"{base_name}_cover_letter.pdf"
        cover_docx = output_dir / f"{base_name}_cover_letter.docx"
        
        # Generate PDFs and DOCX files
        basics = resume_data.get("basics", {}) or {}
        if basics_override:
            # Uploaded resume basics override YAML basics for this request
            basics = {**basics, **(basics_override or {})}
        candidate_name = basics.get("name", "")
        candidate_email = basics.get("email", "")
        candidate_phone = basics.get("phone", "")
        
        pdf_gen.generate_resume_pdf(
            enhanced_resume, str(resume_pdf),
            job_title=job_title, company_name=company_name,
            candidate_name=candidate_name, structured=resume_data
        )
        
        docx_gen.generate_resume_docx(
            enhanced_resume, str(resume_docx),
            job_title=job_title, company_name=company_name,
            candidate_name=candidate_name, structured=resume_data
        )
        
        pdf_gen.generate_cover_letter_pdf(
            cover_letter, str(cover_pdf),
            job_title=job_title,
            company_name=company_name,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
        )
        
        docx_gen.generate_cover_letter_docx(
            cover_letter,
            str(cover_docx),
            job_title=job_title,
            company_name=company_name,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
        )
        
        # Calculate match score
        job_dict = {
            'title': job_title,
            'company': company_name,
            'location': '',
            'description': job_description
        }
        match_score = score_job(job_dict, enhanced_resume)

        # Build human-readable score explanation
        score_explanation = build_score_explanation(
            resume_data=resume_data,
            job_description=job_description,
            match_score=match_score,
            overlapping_skills=overlaps_for_section,
        )
        
        return {
            'success': True,
            'company': company_name,
            'title': job_title,
            'match_score': round(match_score, 1),
            'score_explanation': score_explanation,
            'files': {
                'resume_pdf': str(resume_pdf.relative_to(app.config['OUTPUT_FOLDER'])),
                'resume_docx': str(resume_docx.relative_to(app.config['OUTPUT_FOLDER'])),
                'cover_letter_pdf': str(cover_pdf.relative_to(app.config['OUTPUT_FOLDER'])),
                'cover_letter_docx': str(cover_docx.relative_to(app.config['OUTPUT_FOLDER']))
            },
            'output_dir': str(output_dir.relative_to(app.config['OUTPUT_FOLDER']))
        }, None
        
    except Exception as e:
        return None, f"Error: {str(e)}\n{traceback.format_exc()}"


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    config = load_config()
    return jsonify({
        'status': 'ok',
        'config_loaded': config is not None,
        'llm_providers': {
            'gemini': config.get('gemini', {}).get('enabled', False) if config else False,
            'openai': config.get('openai', {}).get('enabled', False) if config else False,
            'ollama': config.get('ollama', {}).get('enabled', False) if config else False
        },
        'parser_enabled': True
    })


@app.route('/api/generate', methods=['POST'])
def generate():
    """Generate resume and cover letter from job link or description"""
    try:
        data = request.json
        
        # Validate input
        job_link = data.get('job_link', '').strip()
        job_description = data.get('job_description', '').strip()
        company_name = data.get('company', '').strip()
        job_title = data.get('title', '').strip()
        
        if not job_link and not job_description:
            return jsonify({
                'success': False,
                'error': 'Either job_link or job_description is required'
            }), 400
        
        # Load configuration
        config = load_config()
        if not config:
            return jsonify({
                'success': False,
                'error': 'Configuration not found (config.json)'
            }), 500
        
        # Load base resume from YAML
        resume_path = Path("input/resume.yml")
        if not resume_path.exists():
            return jsonify({
                'success': False,
                'error': 'Resume file not found (input/resume.yml)'
            }), 500
        
        _, resume_data = load_resume_data(resume_path)
        if not resume_data:
            return jsonify({
                'success': False,
                'error': 'Failed to load resume data'
            }), 500
        
        # Fetch job description if URL provided
        if job_link:
            job_description = fetch_job_description_from_url(job_link)
            if not job_description:
                return jsonify({
                    'success': False,
                    'error': 'Failed to fetch job description from URL'
                }), 400
            
            # Try to extract company and title from URL
            if not company_name or not job_title:
                extracted_company, extracted_title = extract_job_info_from_url(job_link)
                if not company_name and extracted_company:
                    company_name = extracted_company
                if not job_title and extracted_title:
                    job_title = extracted_title
        
        # Use defaults if still missing
        if not company_name:
            company_name = "Company"
        if not job_title:
            job_title = "Position"
        
        # Generate documents (using YAML-based resume as base)
        result, error = generate_documents(
            job_description=job_description,
            company_name=company_name,
            job_title=job_title,
            resume_data=resume_data,
            config=config,
            base_resume_text=None,
            basics_override=None,
        )
        
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 500
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


@app.route('/api/generate_with_resume', methods=['POST'])
def generate_with_resume():
    """Generate resume & cover letter using an uploaded resume (PDF/DOCX) as base."""
    try:
        # Text fields from form-data
        job_link = (request.form.get('job_link') or "").strip()
        job_description = (request.form.get('job_description') or "").strip()
        company_name = (request.form.get('company') or "").strip()
        job_title = (request.form.get('title') or "").strip()

        resume_file = request.files.get('resume_file')

        if not resume_file or resume_file.filename == '':
            return jsonify({
                'success': False,
                'error': 'Resume file is required when using this option'
            }), 400

        if not job_link and not job_description:
            return jsonify({
                'success': False,
                'error': 'Either job_link or job_description is required'
            }), 400

        # Load configuration
        config = load_config()
        if not config:
            return jsonify({
                'success': False,
                'error': 'Configuration not found (config.json)'
            }), 500

        # Load YAML resume for structured data (name, sections, etc.)
        resume_path = Path("input/resume.yml")
        if not resume_path.exists():
            return jsonify({
                'success': False,
                'error': 'Resume file not found (input/resume.yml)'
            }), 500

        _, resume_data = load_resume_data(resume_path)
        if not resume_data:
            return jsonify({
                'success': False,
                'error': 'Failed to load resume data'
            }), 500

        # Save uploaded resume to disk
        upload_dir = Path(app.config['UPLOAD_FOLDER'])
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', resume_file.filename)
        saved_path = upload_dir / f"{timestamp}_{safe_name}"
        resume_file.save(str(saved_path))

        # Extract text + basics from uploaded resume using shared parser util.
        parsed = parse_resume_file(saved_path)
        base_resume_text = extract_text_from_resume_file(saved_path)

        # If URL provided but no JD text, fetch it
        if job_link and not job_description:
            jd = fetch_job_description_from_url(job_link)
            if not jd:
                return jsonify({
                    'success': False,
                    'error': 'Could not fetch job description from the provided URL'
                }), 400
            job_description = jd

        # Auto-extract company/title from URL when missing
        if job_link:
            auto_company, auto_title = extract_job_info_from_url(job_link)
            if not company_name and auto_company:
                company_name = auto_company
            if not job_title and auto_title:
                job_title = auto_title

        if not company_name:
            company_name = "Company"
        if not job_title:
            job_title = "Position"

        # Generate documents using the uploaded resume text as the base content
        # (for scoring and tailoring), but keep YAML resume_data for any
        # structured fields and fallbacks. Override basics (name, email, phone)
        # from the uploaded resume so the header matches the uploaded file.
        basics_override = parsed.get("basics", {}) or {}
        result, error = generate_documents(
            job_description=job_description,
            company_name=company_name,
            job_title=job_title,
            resume_data=resume_data,
            config=config,
            base_resume_text=base_resume_text,
            basics_override=basics_override,
        )

        if error or not result:
            return jsonify({
                'success': False,
                'error': error or 'Failed to generate documents'
            }), 500

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Server error: {str(e)}"
        }), 500


@app.route('/api/parse_resume', methods=['POST'])
def parse_resume_endpoint():
    """Pure resume parsing endpoint: return structured JSON from uploaded resume."""
    try:
        resume_file = request.files.get('resume_file')
        if not resume_file or resume_file.filename == '':
            return jsonify({
                'success': False,
                'error': 'resume_file is required'
            }), 400

        upload_dir = Path(app.config['UPLOAD_FOLDER'])
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', resume_file.filename)
        saved_path = upload_dir / f"{timestamp}_{safe_name}"
        resume_file.save(str(saved_path))

        parsed = parse_resume_file(saved_path)

        return jsonify({
            'success': True,
            'parsed': parsed
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Server error: {str(e)}"
        }), 500


@app.route('/api/download/<path:filename>')
def download_file(filename):
    """Download generated file"""
    try:
        file_path = Path(app.config['OUTPUT_FOLDER']) / filename
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_path.name
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/preview/<path:filename>')
def preview_file(filename):
    """Preview PDF file in browser"""
    try:
        file_path = Path(app.config['OUTPUT_FOLDER']) / filename
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            file_path,
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("🚀 Quick Apply Web App Starting...")
    print("📝 Make sure config.json is configured with API keys")
    print("📄 Make sure input/resume.yml exists")
    print("\n🌐 Open http://localhost:5000 in your browser")
    print("\nPress Ctrl+C to stop\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

