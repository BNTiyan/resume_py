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
            spaceAfter=6,
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
        Generate a professional 2-page resume PDF
        
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
            
            # Create PDF document
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
            
            # Header with name (extract from first line if not provided)
            name_to_display = candidate_name
            if not name_to_display and content:
                first_line = content.split('\n')[0].strip()
                if first_line and len(first_line) < 50 and not any(kw in first_line.lower() for kw in ['target', 'position', 'github', '@']):
                    name_to_display = first_line
            
            if name_to_display:
                story.append(Paragraph(name_to_display, self.styles['CustomHeader']))
            
            # Contact information
            if 'contact' in sections:
                # Format contact info as a single line if possible
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
                        
                        # Clean up the line
                        clean_line = line.lstrip('•-*►▪→◆ ').strip()
                        
                        if clean_line and len(clean_line) > 20:  # Meaningful content
                            story.append(Paragraph(f"• {clean_line}", self.styles['BulletPoint']))
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
                    
                    if experiences:
                        for exp in experiences[:3]:  # Show top 3 most recent/relevant
                            # Company and position
                            position = exp.get('position', 'Position')
                            company = exp.get('company', 'Company')
                            story.append(Paragraph(
                                f"<b>{position}</b> | {company}",
                                self.styles['CompanyPosition']
                            ))
                            
                            # Date and location
                            date_loc = []
                            if exp.get('dates'):
                                date_loc.append(exp['dates'])
                            if exp.get('location'):
                                date_loc.append(exp['location'])
                            if date_loc:
                                story.append(Paragraph(' | '.join(date_loc), self.styles['DateLocation']))
                            
                            # Key achievements/responsibilities
                            for bullet in exp.get('bullets', [])[:6]:  # Max 6 bullets per job
                                story.append(Paragraph(f"• {bullet}", self.styles['BulletPoint']))
                            
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
            'experience': ['experience', 'employment', 'work history', 'work experience'],
            'education': ['education', 'academic'],
            'skills': ['skills', 'competencies', 'technical skills'],
            'functional_expertise': ['functional expertise', 'functional skills', 'domain expertise'],
            'achievements': ['key achievements', 'achievements', 'accomplishments'],
            'publications': ['publications', 'papers', 'research'],
            'projects': ['projects', 'portfolio', 'key projects'],
            'certifications': ['certifications', 'licenses', 'certificates']
        }
        
        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Skip empty lines at the start of content
            if not current_section and not line_stripped:
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
            
            # Rest goes to summary
            sections['summary'] = content
        
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
        """Parse work experience section into structured data"""
        experiences = []
        current_exp = None
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this looks like a company/position line
            if '|' in line or (any(keyword in line.lower() for keyword in ['engineer', 'developer', 'manager', 'analyst', 'lead', 'architect'])):
                # Save previous experience
                if current_exp and current_exp.get('bullets'):
                    experiences.append(current_exp)
                
                # Start new experience
                current_exp = {'bullets': []}
                
                # Parse company and position
                if '|' in line:
                    parts = line.split('|')
                    current_exp['position'] = parts[0].strip()
                    if len(parts) > 1:
                        current_exp['company'] = parts[1].strip()
                else:
                    current_exp['position'] = line
            
            # Check if this looks like a date/location line
            elif current_exp and any(month in line for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', '20']):
                if '|' in line:
                    parts = line.split('|')
                    current_exp['dates'] = parts[0].strip()
                    if len(parts) > 1:
                        current_exp['location'] = parts[1].strip()
                else:
                    current_exp['dates'] = line
            
            # Otherwise, it's probably a bullet point
            elif current_exp:
                bullet = line.lstrip('•-*►▪→◆ ')
                if bullet and len(bullet) > 15:  # Meaningful content
                    current_exp['bullets'].append(bullet)
        
        # Save last experience
        if current_exp and current_exp.get('bullets'):
            experiences.append(current_exp)
        
        return experiences


# Convenience functions
def generate_resume_pdf(content: str, output_path: str, **kwargs) -> bool:
    """Generate a resume PDF"""
    generator = PDFGenerator()
    return generator.generate_resume_pdf(content, output_path, **kwargs)


def generate_cover_letter_pdf(content: str, output_path: str, **kwargs) -> bool:
    """Generate a cover letter PDF"""
    generator = PDFGenerator()
    return generator.generate_cover_letter_pdf(content, output_path, **kwargs)

