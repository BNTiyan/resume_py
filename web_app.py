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
import re

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


def generate_documents(job_description, company_name, job_title, resume_data, config):
    """Generate resume and cover letter"""
    try:
        # Convert resume to text (base content)
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
                resume_text=resume_text
            )
            tailored_resume = llm_manager.generate(resume_prompt, max_tokens=6000)

            # Generate cover letter with LLM
            cover_letter_prompt = ENHANCED_COVER_LETTER_PROMPT.format(
                company_name=company_name,
                job_title=job_title,
                job_description=job_description,
                resume_text=resume_text
            )
            cover_letter = llm_manager.generate(cover_letter_prompt, max_tokens=1500)
        except Exception as llm_error:
            # LLM completely unavailable (no keys, quotas, etc.) – fall back
            print(f"⚠️ LLM unavailable, falling back to base resume only: {llm_error}")

        # If LLM failed, at least use the base resume text and a simple cover letter template
        if not tailored_resume:
            tailored_resume = resume_text

        if not cover_letter:
            cover_letter = (
                "Dear Hiring Manager,\n\n"
                f"I am very interested in the {job_title} role at {company_name}. "
                "Please find my resume attached, which highlights my experience relevant to this position.\n\n"
                "Thank you for your time and consideration.\n\n"
                "Sincerely,\n"
                f"{resume_data.get('basics', {}).get('name', '')}"
            )
        
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
        candidate_name = resume_data.get("basics", {}).get("name", "")
        
        pdf_gen.generate_resume_pdf(
            tailored_resume, str(resume_pdf),
            job_title=job_title, company_name=company_name,
            candidate_name=candidate_name, structured=resume_data
        )
        
        docx_gen.generate_resume_docx(
            tailored_resume, str(resume_docx),
            job_title=job_title, company_name=company_name,
            candidate_name=candidate_name, structured=resume_data
        )
        
        pdf_gen.generate_cover_letter_pdf(
            cover_letter, str(cover_pdf),
            candidate_name=candidate_name,
            company_name=company_name, job_title=job_title
        )
        
        docx_gen.generate_cover_letter_docx(
            cover_letter, str(cover_docx),
            candidate_name=candidate_name,
            company_name=company_name, job_title=job_title
        )
        
        # Calculate match score
        job_dict = {
            'title': job_title,
            'company': company_name,
            'location': '',
            'description': job_description
        }
        match_score = score_job(job_dict, tailored_resume)
        
        return {
            'success': True,
            'company': company_name,
            'title': job_title,
            'match_score': round(match_score, 1),
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
        }
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
        
        # Load resume
        resume_path = Path("input/resume.yml")
        if not resume_path.exists():
            return jsonify({
                'success': False,
                'error': 'Resume file not found (input/resume.yml)'
            }), 500
        
        resume_text, resume_data = load_resume_data(resume_path)
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
        
        # Generate documents
        result, error = generate_documents(
            job_description, company_name, job_title,
            resume_data, config
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

