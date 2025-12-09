#!/usr/bin/env python3
"""
Quick Apply Web App - Flask Backend (Production-Ready)
Generate tailored resume and cover letter through a web interface
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import json
from pathlib import Path
import traceback
from datetime import datetime
import re

# Create Flask app first
app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'output/web_uploads'
app.config['OUTPUT_FOLDER'] = 'output/web_output'

# Ensure directories exist
try:
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    Path(app.config['OUTPUT_FOLDER']).mkdir(parents=True, exist_ok=True)
    print("✅ Output directories created")
except Exception as e:
    print(f"⚠️  Warning: Could not create directories: {e}")

# Try to import required modules
try:
    from match import (
        fetch_job_description_from_url,
        score_job,
        load_resume_data,
    )
    from enhanced_prompts import ENHANCED_RESUME_PROMPT, ENHANCED_COVER_LETTER_PROMPT
    from pdf_generator import PDFGenerator
    from docx_generator import WordDocumentGenerator
    from llm_manager import LLMManager
    from cover_letter import CoverLetterBuilder
    from resume_utils import render_resume_from_yaml
    print("✅ All modules imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print(f"   Python path: {sys.path}")
    print(f"   Current dir: {os.getcwd()}")
    raise


def load_config():
    """Load configuration from config.json"""
    config_path = Path("config.json")
    if not config_path.exists():
        print("⚠️  config.json not found, using defaults")
        return {
            'gemini': {'enabled': True},
            'openai': {'enabled': False},
            'ollama': {'enabled': False}
        }
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            print("✅ Config loaded successfully")
            return config
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None


def extract_job_info_from_url(url: str):
    """Extract company name and job title from URL"""
    company = None
    title = None
    
    url_lower = url.lower()
    
    if 'greenhouse.io' in url_lower:
        match = re.search(r'boards\.greenhouse\.io/([^/]+)', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
    elif 'lever.co' in url_lower:
        match = re.search(r'jobs\.lever\.co/([^/]+)', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
    elif 'careers.google.com' in url_lower:
        company = "Google"
    else:
        match = re.search(r'https?://(?:www\.|careers\.)?([^/\.]+)', url)
        if match:
            company = match.group(1).title()
    
    return company, title


def generate_documents(job_description, company_name, job_title, resume_data, config):
    """Generate resume and cover letter"""
    try:
        print(f"🤖 Generating documents for {company_name} - {job_title}")
        
        # Initialize LLM Manager
        llm_manager = LLMManager(config)
        
        # Convert resume to text
        resume_text = render_resume_from_yaml(resume_data)
        
        # Generate resume
        resume_prompt = ENHANCED_RESUME_PROMPT.format(
            company_name=company_name,
            job_title=job_title,
            job_description=job_description,
            resume_text=resume_text
        )
        
        print("  📄 Generating resume...")
        tailored_resume = None
        try:
            tailored_resume = llm_manager.generate(resume_prompt, max_tokens=6000)
        except Exception as e:
            print(f"  ⚠️ LLM resume generation failed: {e}")
        if not tailored_resume:
            print("  ⚠️ Falling back to base resume text (no LLM tailoring).")
            tailored_resume = resume_text
        
        # Generate cover letter
        cover_letter_prompt = ENHANCED_COVER_LETTER_PROMPT.format(
            company_name=company_name,
            job_title=job_title,
            job_description=job_description,
            resume_text=resume_text
        )
        
        print("  💌 Generating cover letter...")
        cover_letter = None
        try:
            cover_letter = llm_manager.generate(cover_letter_prompt, max_tokens=1500)
        except Exception as e:
            print(f"  ⚠️ LLM cover letter generation failed: {e}")

        if not cover_letter:
            print("  💌 Falling back to deterministic cover letter builder...")
            candidate_name = resume_data.get("basics", {}).get("name", "")
            builder = CoverLetterBuilder(resume_text, candidate_name)
            cover_letter = builder.compose_concise_text(job_description, company_name, job_title)

        if not cover_letter:
            return None, "Failed to generate cover letter content (LLM + fallback)"
        
        # Generate files
        pdf_gen = PDFGenerator()
        docx_gen = WordDocumentGenerator()
        
        # Create output directory
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
        
        basics = resume_data.get("basics", {}) or {}
        candidate_name = basics.get("name", "")
        candidate_email = basics.get("email", "")
        candidate_phone = basics.get("phone", "")
        
        print("  📑 Generating PDF and DOCX files...")
        
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
            cover_letter,
            str(cover_pdf),
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
        print("  📊 Calculating match score...")
        job_dict = {
            'title': job_title,
            'company': company_name,
            'location': '',
            'description': job_description
        }
        match_score = score_job(job_dict, tailored_resume)
        
        print(f"✅ Documents generated successfully! Match score: {match_score}%")
        
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
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_msg}")
        return None, error_msg


@app.route('/')
def index():
    """Render main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"""
        <html>
        <head><title>Quick Apply - Error</title></head>
        <body>
            <h1>Template Error</h1>
            <p>Error loading template: {str(e)}</p>
            <p>Please ensure templates/index.html exists.</p>
        </body>
        </html>
        """, 500


@app.route('/health')
@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        config = load_config()
        return jsonify({
            'status': 'ok',
            'message': 'Quick Apply Web App is running',
            'config_loaded': config is not None,
            'llm_providers': {
                'gemini': config.get('gemini', {}).get('enabled', False) if config else False,
                'openai': config.get('openai', {}).get('enabled', False) if config else False,
                'ollama': config.get('ollama', {}).get('enabled', False) if config else False
            },
            'env_vars': {
                'GEMINI_API_KEY': 'SET' if os.getenv('GEMINI_API_KEY') else 'NOT_SET',
                'OPENAI_API_KEY': 'SET' if os.getenv('OPENAI_API_KEY') else 'NOT_SET'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/generate', methods=['POST'])
def generate():
    """Generate resume and cover letter from job link or description"""
    try:
        data = request.json
        
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
            
            if not company_name or not job_title:
                extracted_company, extracted_title = extract_job_info_from_url(job_link)
                if not company_name and extracted_company:
                    company_name = extracted_company
                if not job_title and extracted_title:
                    job_title = extracted_title
        
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
            'error': f'Server error: {str(e)}\n{traceback.format_exc()}'
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
    print(f"   Python: {sys.version}")
    print(f"   Working dir: {os.getcwd()}")
    print("📝 Make sure config.json is configured with API keys")
    print("📄 Make sure input/resume.yml exists")
    print("\n🌐 Server will start shortly...\n")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

