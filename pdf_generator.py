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


def _normalize_meta_field(value: str | None) -> str:
    """Normalize company/role/location fields, stripping placeholder text."""
    if not value:
        return ""
    cleaned = value.strip()
    lowered = cleaned.lower()
    if lowered in {"not specified", "not specified."}:
        return ""
    return cleaned


class PDFGenerator:
    """Generate professional PDF documents for resumes and cover letters"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for professional formatting"""
        # Header style
        self.styles.add(ParagraphStyle(
            name='CustomHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subheader style
        self.styles.add(ParagraphStyle(
            name='CustomSubHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold',
            borderWidth=1,
            borderColor=colors.HexColor('#3498db'),
            borderPadding=4,
            backColor=colors.HexColor('#ecf0f1')
        ))
        
        # Contact info style
        self.styles.add(ParagraphStyle(
            name='ContactInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#34495e'),
            alignment=TA_CENTER,
            spaceAfter=12
        ))
        
        # Bullet point style
        self.styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            leftIndent=20,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
            bulletIndent=10
        ))
        
        # Company/Position style
        self.styles.add(ParagraphStyle(
            name='CompanyPosition',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=4,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        ))
        
        # Date/Location style
        self.styles.add(ParagraphStyle(
            name='DateLocation',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=6,
            fontName='Helvetica-Oblique'
        ))
    
    def generate_resume_pdf(
        self,
        content: str,
        output_path: str,
        job_title: str = "",
        company_name: str = "",
        candidate_name: str = ""
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
            # We will try to ensure a minimum of 3 pages by inserting page breaks at logical boundaries
            page_breaks_remaining = 2  # two breaks -> 3 pages total
            
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
            
            # Contact information - extract from content directly
            contact_lines = []
            lines = content.split('\n')
            for line in lines[:10]:  # Check first 10 lines
                line_stripped = line.strip()
                # Look for contact info (email, phone, github, linkedin)
                if '@' in line_stripped or 'github.com' in line_stripped.lower() or 'linkedin.com' in line_stripped.lower() or any(char.isdigit() for char in line_stripped if len(line_stripped) > 7):
                    # Remove markdown links but keep text
                    contact_line = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line_stripped)
                    contact_lines.append(contact_line)
            
            if contact_lines:
                contact_text = ' | '.join(contact_lines)
                story.append(Paragraph(contact_text, self.styles['ContactInfo']))
            elif 'contact' in sections:
                # Fallback to parsed contact
                contact_text = sections['contact'].replace('\n', ' | ')
                story.append(Paragraph(contact_text, self.styles['ContactInfo']))
            
            # Target position (only if both are provided and not "Not specified")
            job_title_normalized = _normalize_meta_field(job_title)
            company_name_normalized = _normalize_meta_field(company_name)
            if job_title_normalized and company_name_normalized:
                story.append(Paragraph(
                    f"<b>Target Position:</b> {job_title_normalized} at {company_name_normalized}",
                    self.styles['Normal']
                ))
                story.append(Spacer(1, 0.2*inch))
            
            # Professional Summary (10 bullet points)
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
                        
                        # Preserve all content exactly - don't filter by length
                        if clean_line:
                            # Escape XML/HTML special chars for ReportLab but preserve text exactly
                            clean_escaped = clean_line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            story.append(Paragraph(f"• {clean_escaped}", self.styles['BulletPoint']))
                            bullet_count += 1
                            if bullet_count >= 10:
                                break
                    
                    if bullet_count > 0:
                        story.append(Spacer(1, 0.15*inch))
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
                    
                    # Try to parse structured experiences
                    experiences = self._parse_experiences(exp_text)
                    # Fallback: loose parse to ensure up to 5 distinct companies render
                    if len(experiences) < 5:
                        loose = self._parse_experiences_loose(exp_text)
                        # merge unique by (position,company)
                        seen = {(e.get('position',''), e.get('company','')) for e in experiences}
                        for e in loose:
                            key = (e.get('position',''), e.get('company',''))
                            if key not in seen and (key[0] or key[1]):
                                experiences.append(e)
                                seen.add(key)
                    
                    # Debug: Print parsed experiences
                    print(f"  [pdf-debug] Parsed {len(experiences)} experiences")
                    for i, exp in enumerate(experiences[:5]):
                        print(f"  [pdf-debug] Exp {i+1}: position='{exp.get('position', 'N/A')}', company='{exp.get('company', 'N/A')}', dates='{exp.get('dates', 'N/A')}', location='{exp.get('location', 'N/A')}'")
                    
                    if experiences:
                        for exp in experiences[:5]:  # Show all 5 companies
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
                                    # Escape XML/HTML special chars for ReportLab but preserve text exactly
                                    # ReportLab Paragraph uses XML-like syntax, so we need to escape &, <, >
                                    bullet_escaped = bullet_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                    story.append(Paragraph(f"• {bullet_escaped}", self.styles['BulletPoint']))
                            
                            story.append(Spacer(1, 0.1*inch))
                        experience_added = True
                    else:
                        # Fallback: just render the text with basic formatting
                        exp_lines = [l.strip() for l in exp_text.split('\n') if l.strip()]
                        for line in exp_lines[:20]:  # Limit to prevent overflow
                            if line.startswith('•') or line.startswith('-'):
                                story.append(Paragraph(line, self.styles['BulletPoint']))
                            else:
                                story.append(Paragraph(line, self.styles['Normal']))
                        story.append(Spacer(1, 0.1*inch))
                        experience_added = True
                    break
            # Insert a page break after Work Experience to help reach 3 pages
            if experience_added and page_breaks_remaining > 0:
                story.append(PageBreak())
                page_breaks_remaining -= 1
            
            # Education
            for key in ['education', 'academic']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("EDUCATION", self.styles['CustomSubHeader']))
                    edu_text = sections[key]
                    edu_lines = [l.strip() for l in edu_text.split('\n') if l.strip()]
                    for line in edu_lines:
                        if line.startswith('•') or line.startswith('-'):
                            story.append(Paragraph(line, self.styles['BulletPoint']))
                        else:
                            story.append(Paragraph(line, self.styles['Normal']))
                    story.append(Spacer(1, 0.15*inch))
                    break
            
            # Skills
            for key in ['skills', 'technical_skills', 'competencies']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("TECHNICAL SKILLS", self.styles['CustomSubHeader']))
                    skills_text = sections[key]
                    # Remove --- separators
                    skills_text = skills_text.replace('---', '').strip()
                    if skills_text:
                        story.append(Paragraph(skills_text, self.styles['Normal']))
                        story.append(Spacer(1, 0.15*inch))
                    # Optional second page break after skills if still needed
                    if page_breaks_remaining > 0:
                        story.append(PageBreak())
                        page_breaks_remaining -= 1
                    break
            
            # Functional Expertise
            for key in ['functional_expertise', 'functional_skills', 'domain_expertise']:
                if key in sections and sections[key].strip():
                    story.append(Paragraph("FUNCTIONAL EXPERTISE", self.styles['CustomSubHeader']))
                    expertise_text = sections[key].replace('---', '').strip()
                    if expertise_text:
                        story.append(Paragraph(expertise_text, self.styles['Normal']))
                        story.append(Spacer(1, 0.15*inch))
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
                    story.append(Spacer(1, 0.15*inch))
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
                    story.append(Spacer(1, 0.15*inch))
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
                    story.append(Spacer(1, 0.15*inch))
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
                    break
            
            # Build PDF
            # If we still haven't reached 3 pages, add remaining page breaks at the end
            while page_breaks_remaining > 0:
                story.append(PageBreak())
                page_breaks_remaining -= 1
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
                story.append(Spacer(1, 0.2*inch))
            
            # Subject line (only if both are provided and not "Not specified")
            job_title_normalized = _normalize_meta_field(job_title)
            if (job_title_normalized and company_name_normalized):
                story.append(Paragraph(
                    f"<b>Re: Application for {job_title_normalized} Position</b>",
                    self.styles['Normal']
                ))
                story.append(Spacer(1, 0.2*inch))
            
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
            story.append(Spacer(1, 0.3*inch))
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
            r'this resume is.*optimized',
            r'tailored.*for.*position',
            r'optimized for.*position at',
        ]
        
        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Skip empty lines at the start of content
            if not current_section and not line_stripped:
                continue
            
            # Skip lines matching optimization text patterns
            if any(re.search(pattern, line_lower) for pattern in skip_patterns):
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
        """Parse work experience section into structured data - preserves exact text"""
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

