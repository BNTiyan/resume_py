"""
PDF Generator for Resumes and Cover Letters
Generates professional 2-page resumes and 1-page cover letters in PDF format
"""
import os
from typing import Optional
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime
import re

try:
    from llm_experience_parser import parse_experiences_with_llm
    LLM_PARSER_AVAILABLE = True
except ImportError:
    LLM_PARSER_AVAILABLE = False


def _normalize_meta_field(value: str | None) -> str:
    """Normalize company/role/location fields, stripping placeholder text."""
    if not value:
        return ""
    cleaned = value.strip()
    lowered = cleaned.lower()
    if lowered in {"not specified", "not specified."}:
        return ""
    return cleaned


def _clean_markdown(text: str) -> str:
    """Remove markdown formatting (bold, italic, etc.) from text."""
    if not text:
        return text
    # Convert markdown links [label](url) into "label: url"
    def _link_repl(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        url = match.group(2).strip()
        if not label:
            return url
        # Standardize common profile labels
        if label.lower() in {"github", "linkedin", "portfolio", "website"}:
            return f"{label}: {url}"
        return f"{label} ({url})"

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link_repl, text)
    # Remove bold (**text** or __text__)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    # Remove italic (*text* or _text_) - be careful not to remove list bullets
    text = re.sub(r'(?<!\*)\*(?!\*)([^\*]+)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_(?!_)([^_]+)_(?!_)', r'\1', text)
    return text

LINK_REGEX = re.compile(r'https?://[^\s,;]+', re.IGNORECASE)
UNWANTED_PHRASES = [
    "this resume is crafted to align bhavana's extensive technical",
    "this resume is crafted to align bhavana's extensive technical background",
]


def _extract_contact_details(content: str, sections: dict) -> dict[str, str]:
    """Extract email, phone, LinkedIn, and GitHub links from content/sections."""
    details: dict[str, str] = {}
    candidates = []
    candidates.extend(content.splitlines()[:30])
    contact_section = sections.get("contact")
    if contact_section:
        candidates.extend(contact_section.splitlines())

    email_regex = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    phone_regex = re.compile(r'(\+?\d[\d\s\-\(\)]{7,}\d)')
    for line in candidates:
        if not line:
            continue
        stripped = _clean_markdown(line.strip())
        lower = stripped.lower()
        if "linkedin.com" in lower and "linkedin" not in details:
            match = LINK_REGEX.search(stripped)
            details["linkedin"] = match.group(0) if match else stripped
            continue
        if "github.com" in lower and "github" not in details:
            match = LINK_REGEX.search(stripped)
            details["github"] = match.group(0) if match else stripped
            continue
        if "email" in lower:
            match = email_regex.search(stripped)
            if match:
                details.setdefault("email", match.group(0))
        else:
            match = email_regex.search(stripped)
            if match and "email" not in details:
                details["email"] = match.group(0)
        match_phone = phone_regex.search(stripped)
        if match_phone and "phone" not in details:
            details["phone"] = re.sub(r'\s+', ' ', match_phone.group(0)).strip()
    return details


class PDFGenerator:
    """Generate professional PDF documents for resumes and cover letters"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _experiences_from_structured(self, work_items: list[dict]) -> list[dict]:
        """Build experiences list from structured YAML work entries."""
        results: list[dict] = []
        if not work_items:
            return results
        for job in work_items:
            try:
                position = (job.get("position") or job.get("title") or "").strip()
                company = (job.get("company") or "").strip()
                start = job.get("startDate") or job.get("start_date") or ""
                end = job.get("endDate") or job.get("end_date") or ""
                dates = " – ".join([p for p in [start, end] if p]).strip()
                location = (job.get("location") or "").strip()
                # Merge responsibilities and highlights into bullets
                bullets: list[str] = []
                for key in ("responsibilities", "highlights"):
                    vals = job.get(key) or []
                    if isinstance(vals, list):
                        bullets.extend([str(v).strip() for v in vals if str(v).strip()])
                # Also include 'summary'/'achievements' if present
                for key in ("achievements",):
                    vals = job.get(key) or []
                    if isinstance(vals, list):
                        bullets.extend([str(v).strip() for v in vals if str(v).strip()])
                results.append({
                    "position": position,
                    "company": company,
                    "dates": dates,
                    "location": location,
                    "bullets": bullets,
                })
            except Exception:
                continue
        return results
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for professional formatting"""
        # Header style
        self.styles.add(ParagraphStyle(
            name='CustomHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=3,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subheader style
        self.styles.add(ParagraphStyle(
            name='CustomSubHeader',
            parent=self.styles['Heading2'],
            fontSize=11,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=4,
            spaceBefore=6,
            fontName='Helvetica-Bold',
            borderWidth=1,
            borderColor=colors.HexColor('#3498db'),
            borderPadding=2,
            backColor=colors.HexColor('#ecf0f1')
        ))
        
        # Contact info style
        self.styles.add(ParagraphStyle(
            name='ContactInfo',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#34495e'),
            alignment=TA_CENTER,
            spaceAfter=6
        ))
        
        # Bullet point style
        self.styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#2c3e50'),
            leftIndent=20,
            spaceAfter=3,
            alignment=TA_JUSTIFY,
            bulletIndent=10
        ))
        
        # Company/Position style
        self.styles.add(ParagraphStyle(
            name='CompanyPosition',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=2,
            spaceBefore=4,
            fontName='Helvetica-Bold'
        ))
        
        # Date/Location style
        self.styles.add(ParagraphStyle(
            name='DateLocation',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=3,
            fontName='Helvetica-Oblique'
        ))
    
    def generate_resume_pdf(
        self,
        content: str,
        output_path: str,
        job_title: str = "",
        company_name: str = "",
        candidate_name: str = "",
        structured: dict | None = None
    ) -> bool:
        """
r45        Generate a professional 3-page resume PDF
        
        Args:
            content: Resume text content
            output_path: Path to save the PDF
            job_title: Target job title
            company_name: Target company name
            candidate_name: Candidate's name
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Create PDF document (3 pages allowed)
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )
            
            # Build content
            story = []
            
            # Parse and format the resume content
            sections = self._parse_resume_content(content)
            
            # Debug: print what sections were found
            print(f"  [pdf-debug] Found sections: {list(sections.keys())}")
            
            # If parsing failed or content seems corrupted, use raw rendering mode
            use_raw_mode = False
            if not sections or len(sections) < 2:
                print(f"  [pdf-debug] ⚠️ Few sections found, checking if raw mode needed...")
                # Check if content looks like it's already well-formatted
                if 'PROFESSIONAL SUMMARY' in content or 'WORK EXPERIENCE' in content:
                    use_raw_mode = True
                    print(f"  [pdf-debug] Using raw rendering mode to preserve exact content")
            
            # Extract name from content (look for bold name or first line)
            name_to_display = candidate_name
            if not name_to_display and content:
                lines = content.split('\n')
                # Look for name in first few lines (might be bold with **)
                for line in lines[:5]:
                    line_stripped = line.strip()
                    # Check if it's a name (not too long, doesn't contain email/github markers)
                    if line_stripped and len(line_stripped) < 50:
                        # Remove markdown bold markers
                        name_candidate = line_stripped.replace('**', '').strip()
                        if name_candidate and not any(kw in name_candidate.lower() for kw in ['target', 'position', 'github', '@', 'linkedin', 'http', 'www']):
                            # Check if it looks like a name (has capital letters, not all caps)
                            if name_candidate[0].isupper() and not name_candidate.isupper():
                                name_to_display = name_candidate
                                break
            
            if name_to_display:
                story.append(Paragraph(name_to_display, self.styles['CustomHeader']))
            
            contact_details = _extract_contact_details(content, sections)
            
            # Use structured data if available to override extracted details
            if structured and structured.get("basics"):
                basics = structured["basics"]
                if basics.get("email"):
                    contact_details["email"] = basics["email"]
                if basics.get("phone"):
                    contact_details["phone"] = basics["phone"]
                if basics.get("profiles"):
                    for profile in basics["profiles"]:
                        network = profile.get("network", "").lower()
                        if network == "github":
                            contact_details["github"] = profile.get("url")
                        elif network == "linkedin":
                            contact_details["linkedin"] = profile.get("url")

            # Display contact info on separate lines
            if contact_details.get("email"):
                story.append(Paragraph(contact_details["email"], self.styles['ContactInfo']))
            if contact_details.get("phone"):
                story.append(Paragraph(contact_details["phone"], self.styles['ContactInfo']))
            if contact_details.get("github"):
                story.append(Paragraph(contact_details["github"], self.styles['ContactInfo']))
            if contact_details.get("linkedin"):
                story.append(Paragraph(contact_details["linkedin"], self.styles['ContactInfo']))
            
            # Add spacing after contact info
            if contact_details:
                story.append(Spacer(1, 0.15*inch))
            
            # Professional Summary (15 bullet points)
            summary_added = False
            for key in ['summary', 'professional_summary', 'objective']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("PROFESSIONAL SUMMARY", self.styles['CustomSubHeader']))
                    summary_text = sections[key]
                    
                    # Extract bullets - look for lines that start with bullet or are substantial
                    summary_lines = [l.strip() for l in summary_text.split('\n') if l.strip()]
                    bullet_count = 0
                    
                    for line in summary_lines:
                        # Skip if it's just a section header
                        if line.isupper() and len(line) < 50:
                            continue
                        
                        # Preserve exact text - only remove leading bullet char if present
                        clean_line = line.lstrip('•-*►▪→◆ ').strip()
                        
                        # Remove markdown formatting
                        clean_line = _clean_markdown(clean_line)
                        
                        # Preserve all content exactly - don't filter by length
                        if clean_line:
                            # Escape XML/HTML special chars for ReportLab but preserve text exactly
                            clean_escaped = clean_line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            story.append(Paragraph(f"• {clean_escaped}", self.styles['BulletPoint']))
                            bullet_count += 1
                            if bullet_count >= 15:
                                break
                    
                    if bullet_count > 0:
                        story.append(Spacer(1, 0.06*inch))
                        summary_added = True
                    break
            
            # If no summary found, create one from the first substantial paragraphs
            if not summary_added:
                story.append(Paragraph("PROFESSIONAL SUMMARY", self.styles['CustomSubHeader']))
                story.append(Paragraph("Experienced professional seeking to contribute expertise to this role.", self.styles['Normal']))
                story.append(Spacer(1, 0.15*inch))
            
            # Work Experience (most recent, relevant to job)
            experience_added = False
            for key in ['experience', 'work_experience', 'employment']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("WORK EXPERIENCE", self.styles['CustomSubHeader']))
                    exp_text = sections[key]
                    
                    # If structured data provided, prefer structured work history
                    experiences = []
                    if structured and isinstance(structured.get("work"), list):
                        experiences = self._experiences_from_structured(structured.get("work"))
                    
                    # Otherwise try to parse experiences from text
                    if not experiences:
                        experiences = self._parse_experiences(exp_text)
                    # Fallbacks: ensure up to 5 distinct experiences by merging from section and then whole content
                    def _merge_unique(base: list, extra: list) -> list:
                        seen_local = {(b.get('position',''), b.get('company','')) for b in base}
                        for e in extra:
                            key = (e.get('position',''), e.get('company',''))
                            if key not in seen_local and (key[0] or key[1]):
                                base.append(e)
                                seen_local.add(key)
                        return base
                    if len(experiences) < 5:
                        # Merge loose parse from the experience section
                        experiences = _merge_unique(experiences, self._parse_experiences_loose(exp_text))
                    if len(experiences) < 5:
                        # As a final safety, merge from the entire resume content
                        experiences = _merge_unique(experiences, self._parse_experiences_loose(content))
                    
                    # Debug: Print parsed experiences
                    print(f"  [pdf-debug] Parsed {len(experiences)} experiences")
                    for i, exp in enumerate(experiences[:5]):
                        print(f"  [pdf-debug] Exp {i+1}: position='{exp.get('position', 'N/A')}', company='{exp.get('company', 'N/A')}', dates='{exp.get('dates', 'N/A')}', location='{exp.get('location', 'N/A')}'")
                    
                    if experiences:
                        for exp in experiences[:5]:  # Show up to 5 companies
                            # Role and Company - preserve exact format from text
                            position = exp.get('position', '').strip()
                            company = exp.get('company', '').strip()
                            
                            # Reconstruct the exact line format: "Position | Company"
                            if position and company:
                                exp_header = f"<b>{position}</b> | {company}"
                            elif position:
                                exp_header = f"<b>{position}</b>"
                            elif company:
                                exp_header = company
                            else:
                                continue  # Skip if no position or company
                            
                            story.append(Paragraph(exp_header, self.styles['CompanyPosition']))
                            
                            # Date and location - preserve exact format
                            date_loc = []
                            if exp.get('dates'):
                                date_loc.append(exp['dates'].strip())
                            if exp.get('location'):
                                date_loc.append(exp['location'].strip())
                            if date_loc:
                                story.append(Paragraph(' | '.join(date_loc), self.styles['DateLocation']))
                            
                            # Key achievements/responsibilities - preserve exact text
                            for bullet in exp.get('bullets', []):  # Show all bullets, no limit
                                # Preserve the exact bullet text without modification
                                bullet_text = bullet.strip()
                                if bullet_text:
                                    # Remove markdown formatting
                                    bullet_text = _clean_markdown(bullet_text)
                                    # Escape XML/HTML special chars for ReportLab but preserve text exactly
                                    # ReportLab Paragraph uses XML-like syntax, so we need to escape &, <, >
                                    bullet_escaped = bullet_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                    story.append(Paragraph(f"• {bullet_escaped}", self.styles['BulletPoint']))
                            
                            story.append(Spacer(1, 0.04*inch))
                        experience_added = True
                    else:
                        # Fallback: just render the text with basic formatting
                        exp_lines = [l.strip() for l in exp_text.split('\n') if l.strip()]
                        for line in exp_lines[:20]:  # Limit to prevent overflow
                            line = _clean_markdown(line)
                            if line.startswith('•') or line.startswith('-'):
                                story.append(Paragraph(line, self.styles['BulletPoint']))
                            else:
                                story.append(Paragraph(line, self.styles['Normal']))
                        story.append(Spacer(1, 0.1*inch))
                        experience_added = True
                    break
            
            # Education
            for key in ['education', 'academic']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("EDUCATION", self.styles['CustomSubHeader']))
                    edu_text = sections[key]
                    edu_lines = [l.strip() for l in edu_text.split('\n') if l.strip()]
                    for line in edu_lines:
                        line = _clean_markdown(line)
                        if line.startswith('•') or line.startswith('-'):
                            story.append(Paragraph(line, self.styles['BulletPoint']))
                        else:
                            story.append(Paragraph(line, self.styles['Normal']))
                    story.append(Spacer(1, 0.06*inch))
                    break
            
            # Skills
            for key in ['skills', 'technical_skills', 'competencies']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("TECHNICAL SKILLS", self.styles['CustomSubHeader']))
                    skills_text = sections[key]
                    # Remove --- separators
                    skills_text = skills_text.replace('---', '').strip()
                    if skills_text:
                        # Parse skills into bullet points
                        skills_lines = [l.strip() for l in skills_text.split('\n') if l.strip()]
                        for line in skills_lines:
                            line = _clean_markdown(line)
                            # Check if line already has bullet or is a category
                            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                                clean_text = line.lstrip('•-*►▪→◆ ').strip()
                                if clean_text:  # Only add if there's actual content
                                    story.append(Paragraph(line, self.styles['BulletPoint']))
                            elif ':' in line and len(line) < 200:
                                # Category line like "Programming Languages: Python, C++"
                                story.append(Paragraph(f"• {line}", self.styles['BulletPoint']))
                            else:
                                # Plain text - add bullet
                                if line:  # Only add if not empty
                                    story.append(Paragraph(f"• {line}", self.styles['BulletPoint']))
                        story.append(Spacer(1, 0.06*inch))
                    break
            
            # Functional Expertise
            for key in ['functional_expertise', 'functional_skills', 'domain_expertise']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("FUNCTIONAL EXPERTISE", self.styles['CustomSubHeader']))
                    expertise_text = sections[key].replace('---', '').strip()
                    if expertise_text:
                        # Parse expertise into bullet points
                        expertise_lines = [l.strip() for l in expertise_text.split('\n') if l.strip()]
                        for line in expertise_lines:
                            line = _clean_markdown(line)
                            # Check if line already has bullet or is a category
                            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                                clean_text = line.lstrip('•-*►▪→◆ ').strip()
                                if clean_text:  # Only add if there's actual content
                                    story.append(Paragraph(line, self.styles['BulletPoint']))
                            elif ':' in line and len(line) < 200:
                                # Category line like "Machine Learning & AI: ML pipeline development"
                                story.append(Paragraph(f"• {line}", self.styles['BulletPoint']))
                            else:
                                # Plain text - add bullet
                                if line:  # Only add if not empty
                                    story.append(Paragraph(f"• {line}", self.styles['BulletPoint']))
                        story.append(Spacer(1, 0.06*inch))
                    break
            
            # Key Achievements
            for key in ['achievements', 'key_achievements', 'accomplishments']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("KEY ACHIEVEMENTS", self.styles['CustomSubHeader']))
                    achievement_text = sections[key]
                    achievement_lines = [l.strip() for l in achievement_text.split('\n') if l.strip()]
                    for line in achievement_lines[:10]:  # Max 10 achievements
                        if line.startswith('•') or line.startswith('-'):
                            story.append(Paragraph(line, self.styles['BulletPoint']))
                        else:
                            story.append(Paragraph(line, self.styles['Normal']))
                    story.append(Spacer(1, 0.06*inch))
                    break
            
            # Publications
            for key in ['publications', 'papers', 'research']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("PUBLICATIONS", self.styles['CustomSubHeader']))
                    pub_text = sections[key]
                    pub_lines = [l.strip() for l in pub_text.split('\n') if l.strip()]
                    for line in pub_lines:
                        if line.startswith('•') or line.startswith('-'):
                            story.append(Paragraph(line, self.styles['BulletPoint']))
                        else:
                            story.append(Paragraph(line, self.styles['Normal']))
                    story.append(Spacer(1, 0.06*inch))
                    break
            
            # Projects (if space allows)
            for key in ['projects', 'key_projects']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("KEY PROJECTS", self.styles['CustomSubHeader']))
                    proj_text = sections[key]
                    proj_lines = [l.strip() for l in proj_text.split('\n') if l.strip()]
                    for line in proj_lines[:10]:  # Limit to prevent overflow
                        if line.startswith('•') or line.startswith('-'):
                            story.append(Paragraph(line, self.styles['BulletPoint']))
                        else:
                            story.append(Paragraph(line, self.styles['Normal']))
                    story.append(Spacer(1, 0.06*inch))
                    break
            
            # Certifications
            for key in ['certifications', 'certificates']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("CERTIFICATIONS", self.styles['CustomSubHeader']))
                    cert_text = sections[key]
                    cert_lines = [l.strip() for l in cert_text.split('\n') if l.strip()]
                    for line in cert_lines:
                        if line.startswith('•') or line.startswith('-'):
                            story.append(Paragraph(line, self.styles['BulletPoint']))
                        else:
                            story.append(Paragraph(line, self.styles['Normal']))
                    story.append(Spacer(1, 0.06*inch))
                    break
            
            # Build PDF
            # If we still haven't reached 3 pages, add remaining page breaks at the end
            doc.build(story)
            print(f"[pdf] ✅ Resume PDF generated: {output_path}")
            return True
            
        except Exception as e:
            print(f"[pdf] ❌ Error generating resume PDF: {e}")
            return False
    
    def generate_cover_letter_pdf(
        self,
        content: str,
        output_path: str,
        job_title: str = "",
        company_name: str = "",
        candidate_name: str = "",
        candidate_email: str = "",
        candidate_phone: str = ""
    ) -> bool:
        """
        Generate a professional 1-page cover letter PDF
        
        Args:
            content: Cover letter text content
            output_path: Path to save the PDF
            job_title: Target job title
            company_name: Target company name
            candidate_name: Candidate's name
            candidate_email: Candidate's email
            candidate_phone: Candidate's phone
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=inch,
                leftMargin=inch,
                topMargin=inch,
                bottomMargin=inch
            )
            
            story = []
            
            # Header with contact info
            if candidate_name:
                story.append(Paragraph(candidate_name, self.styles['CustomHeader']))
            
            contact_parts = []
            if candidate_email:
                contact_parts.append(candidate_email)
            if candidate_phone:
                contact_parts.append(candidate_phone)
            if contact_parts:
                story.append(Paragraph(' | '.join(contact_parts), self.styles['ContactInfo']))
            
            # Date
            story.append(Paragraph(
                datetime.now().strftime("%B %d, %Y"),
                self.styles['Normal']
            ))
            story.append(Spacer(1, 0.2*inch))
            
            # Hiring manager address (only if company name is valid and not "Not specified")
            company_name_normalized = _normalize_meta_field(company_name)
            if company_name_normalized:
                story.append(Paragraph(f"Hiring Manager<br/>{company_name_normalized}", self.styles['Normal']))
                story.append(Spacer(1, 0.08*inch))
            
            # Subject line (only if both are provided and not "Not specified")
            job_title_normalized = _normalize_meta_field(job_title)
            if (job_title_normalized and company_name_normalized):
                story.append(Paragraph(
                    f"<b>Re: Application for {job_title_normalized} Position</b>",
                    self.styles['Normal']
                ))
                story.append(Spacer(1, 0.08*inch))
            
            # Cover letter body
            # Parse paragraphs and format, removing "Not specified" text
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            for para in paragraphs:
                # Remove "Not specified" references
                para = para.replace("Not specified.", "").replace("Not specified", "")
                para = para.replace("Re: Application for Not specified. Position", "")
                para = para.replace("Re: Application for Not specified Position", "")
                para = re.sub(r'\s+', ' ', para).strip()  # Clean up extra spaces
                
                if not para:  # Skip empty paragraphs after cleaning
                    continue
                    
                # Skip if it looks like a header or signature
                if para.lower().startswith(('dear', 'sincerely', 'best regards')):
                    story.append(Paragraph(para, self.styles['Normal']))
                else:
                    story.append(Paragraph(para, self.styles['BodyText']))
                story.append(Spacer(1, 0.15*inch))
            
            # Closing
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph("Sincerely,", self.styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
            if candidate_name:
                story.append(Paragraph(candidate_name, self.styles['Normal']))
            
            # Build PDF
            doc.build(story)
            print(f"[pdf] ✅ Cover letter PDF generated: {output_path}")
            return True
            
        except Exception as e:
            print(f"[pdf] ❌ Error generating cover letter PDF: {e}")
            return False
    
    def _parse_resume_content(self, content: str) -> dict:
        """Parse resume text content into sections"""
        sections = {}
        current_section = None
        current_content = []
        
        lines = content.split('\n')
        
        # Common section headers (case-insensitive)
        section_keywords = {
            'contact': ['contact', 'email:', 'phone:', 'github:', 'linkedin:'],
            'summary': ['summary', 'objective', 'profile', 'professional summary'],
            'experience': ['experience', 'employment', 'work history', 'work experience', 'professional experience'],
            'education': ['education', 'academic'],
            'skills': ['skills', 'competencies', 'technical skills'],
            'functional_expertise': ['functional expertise', 'functional skills', 'domain expertise'],
            'achievements': ['key achievements', 'achievements', 'accomplishments'],
            'publications': ['publications', 'papers', 'research'],
            'projects': ['projects', 'portfolio', 'key projects'],
            'certifications': ['certifications', 'licenses', 'certificates']
        }
        
        # Patterns to skip (optimization text, meta descriptions, etc.)
        skip_patterns = [
            r'specifically optimized for',
            r'highlighting.*relevant skills',
            r'this resume (is|has been).*optimized',
            r'this resume (is|has been).*tailored',
            r'this resume (is|has been).*designed',
            r'this resume (is|has been).*crafted',
            r'tailored.*for.*position',
            r'optimized for.*position at',
            r'formatted to align with',
            r'designed to showcase',
            r'this resume is crafted to align ',
        ]
        
        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Skip empty lines at the start of content
            if not current_section and not line_stripped:
                continue
            
            # Skip horizontal separator lines (---, ===, etc.)
            if line_stripped and all(c in '-=_*~' for c in line_stripped):
                continue
            
            # Remove markdown bold syntax (**text**)
            line_stripped = re.sub(r'\*\*(.*?)\*\*', r'\1', line_stripped)
            
            # Skip lines matching optimization text patterns
            if any(re.search(pattern, line_lower) for pattern in skip_patterns):
                continue

            if any(phrase in line_lower for phrase in UNWANTED_PHRASES):
                continue
            
            # Check if this is a section header (all caps or specific keywords)
            is_section_header = False
            found_section = None
            
            # Check for all-caps section headers
            if line_stripped.isupper() and len(line_stripped) > 3:
                for section_key, keywords in section_keywords.items():
                    if any(keyword in line_lower for keyword in keywords):
                        is_section_header = True
                        found_section = section_key
                        break
            
            # Check for section keywords
            if not is_section_header:
                for section_key, keywords in section_keywords.items():
                    if any(line_lower.startswith(keyword) or line_lower == keyword for keyword in keywords):
                        is_section_header = True
                        found_section = section_key
                        break
            
            if is_section_header and found_section:
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                current_section = found_section
                current_content = []
            elif current_section:
                # Add to current section
                current_content.append(line)
            else:
                # Before any section (might be header/contact info)
                if 'github:' in line_lower or 'linkedin:' in line_lower or '@' in line:
                    if 'contact' not in sections:
                        sections['contact'] = line_stripped
                    else:
                        sections['contact'] += '\n' + line_stripped
        
        # Save last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        # If no sections found, try to extract from raw content
        if not sections:
            # Try to find contact info
            for line in lines[:10]:  # Check first 10 lines
                if '@' in line or 'github' in line.lower() or 'linkedin' in line.lower():
                    sections['contact'] = line.strip()
                    break
            
            # Rest goes to summary (but filter out optimization text)
            filtered_content = '\n'.join([
                line for line in lines 
                if not any(re.search(pattern, line.lower()) for pattern in skip_patterns)
            ])
            sections['summary'] = filtered_content
        
        return sections
    
    def _extract_bullet_points(self, text: str, max_bullets: int = 10) -> list:
        """Extract bullet points from text"""
        bullets = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            # Remove existing bullet characters
            line = line.lstrip('•-*►▪→◆ ')
            if line and len(line) > 10:  # Meaningful content
                bullets.append(line)
                if len(bullets) >= max_bullets:
                    break
        
        return bullets
    
    def _parse_experiences(self, text: str) -> list:
        """Parse work experience section into structured data - uses LLM when available"""
        # Try LLM parsing first if available
        if LLM_PARSER_AVAILABLE:
            try:
                print("[pdf-debug] Attempting LLM-based experience parsing...")
                llm_experiences = parse_experiences_with_llm(text)
                if llm_experiences:
                    print(f"[pdf-debug] LLM parsed {len(llm_experiences)} experiences successfully")
                    # Debug output
                    for idx, exp in enumerate(llm_experiences, 1):
                        print(f"  [pdf-debug] Exp {idx}: position={exp.get('position')!r}, company={exp.get('company')!r}, dates={exp.get('dates')!r}, location={exp.get('location')!r}")
                    return llm_experiences
                else:
                    print("[pdf-debug] LLM parsing returned no results, falling back to regex parser")
            except Exception as e:
                print(f"[pdf-debug] LLM parsing failed: {e}, falling back to regex parser")
        
        # Fallback to original regex-based parsing
        print("[pdf-debug] Using regex-based experience parsing...")
        experiences = []
        current_exp = None
        
        lines = text.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # Check if this looks like a company/position line (has | separator or bold markers)
            is_position_line = False
            if '|' in line_stripped:
                is_position_line = True
            elif line_stripped.startswith('**') and line_stripped.endswith('**'):
                # Markdown bold - likely a position/company header
                is_position_line = True
            elif any(keyword in line_stripped.lower() for keyword in ['engineer', 'developer', 'manager', 'analyst', 'lead', 'architect', 'scientist', 'consultant', 'owner', 'master', 'scrum']) and len(line_stripped) < 100:
                # Short line with job keywords - likely position header
                is_position_line = True
            
            if is_position_line:
                # Save previous experience (even if no bullets, as long as we have position/company)
                if current_exp and (current_exp.get('position') or current_exp.get('company')):
                    experiences.append(current_exp)
                
                # Start new experience
                current_exp = {'bullets': []}
                
                # Parse company and position - preserve exact text
                if '|' in line_stripped:
                    parts = [p.strip() for p in line_stripped.split('|')]
                    # Company is always the LAST part, position is everything before it
                    if len(parts) >= 2:
                        # Remove markdown bold markers but preserve text
                        position_parts = [p.replace('**', '').strip() for p in parts[:-1]]
                        company_part = parts[-1].replace('**', '').strip()
                        current_exp['position'] = ' | '.join(position_parts)  # All parts except last
                        current_exp['company'] = company_part  # Last part is company
                    elif len(parts) == 1:
                        current_exp['position'] = parts[0].replace('**', '').strip()
                else:
                    # Remove markdown bold markers
                    current_exp['position'] = line_stripped.replace('**', '').strip()
            
            # Check if this looks like a date/location line
            elif current_exp and (any(month in line_stripped for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', '20']) or 'Present' in line_stripped or '–' in line_stripped or ('-' in line_stripped and any(month in line_stripped for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']))):
                # Preserve exact date/location format
                if '|' in line_stripped:
                    parts = [p.strip() for p in line_stripped.split('|')]
                    current_exp['dates'] = parts[0].strip()
                    if len(parts) > 1:
                        current_exp['location'] = parts[1].strip()
                else:
                    # Check if it's a date range (contains – or -)
                    if '–' in line_stripped or ('-' in line_stripped and any(month in line_stripped for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])):
                        current_exp['dates'] = line_stripped
                    elif any(month in line_stripped for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                        current_exp['dates'] = line_stripped
                    else:
                        current_exp['location'] = line_stripped
            
            # Otherwise, it's probably a bullet point - preserve EXACT text
            elif current_exp:
                # Preserve the exact bullet text - only remove leading bullet char if present
                bullet = line_stripped.lstrip('•-*►▪→◆ ').strip()
                # Preserve all content exactly - don't filter by length
                if bullet:
                    # Don't modify the text - preserve "AI", "I", etc. exactly as written
                    current_exp['bullets'].append(bullet)
        
        # Save last experience (even if no bullets, as long as we have position/company)
        if current_exp and (current_exp.get('position') or current_exp.get('company')):
            experiences.append(current_exp)
        
        return experiences

    def _parse_experiences_loose(self, text: str) -> list:
        """Looser parser: capture any line with a ' | ' as position|company and attach following bullets/dates."""
        results = []
        current = None
        for line in text.split('\n'):
            s = line.strip()
            if not s:
                continue
            if '|' in s:
                # potential header
                parts = [p.strip().replace('**','') for p in s.split('|')]
                if len(parts) >= 2:
                    # save previous
                    if current and (current.get('position') or current.get('company')):
                        results.append(current)
                    current = {'position': ' | '.join(parts[:-1]), 'company': parts[-1], 'bullets': []}
                    continue
            # date/location
            if current and (any(m in s for m in ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Present']) or '–' in s or '-' in s):
                if '|' in s:
                    p = [p.strip() for p in s.split('|')]
                    current['dates'] = p[0]
                    if len(p) > 1:
                        current['location'] = p[1]
                else:
                    current['dates'] = s
                continue
            # bullets
            if current:
                b = s.lstrip('•-*►▪→◆ ').strip()
                if b:
                    current.setdefault('bullets', []).append(b)
        if current and (current.get('position') or current.get('company')):
            results.append(current)
        return results


# Convenience functions
def generate_resume_pdf(content: str, output_path: str, **kwargs) -> bool:
    """Generate a resume PDF"""
    generator = PDFGenerator()
    return generator.generate_resume_pdf(content, output_path, **kwargs)


def generate_cover_letter_pdf(content: str, output_path: str, **kwargs) -> bool:
    """Generate a cover letter PDF"""
    generator = PDFGenerator()
    return generator.generate_cover_letter_pdf(content, output_path, **kwargs)

