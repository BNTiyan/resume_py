"""
LLM-based job description extractor that works without embeddings.
Extracts structured information from raw job page HTML/text.
"""
import os
import re
from typing import Dict, Optional

try:
    import openai_compat  # noqa: F401
except Exception:
    openai_compat = None

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False
    genai = None

load_dotenv()


class JobDescriptionExtractor:
    """
    Extract structured job information using LLM without requiring embeddings.
    Looks for common patterns like responsibilities, qualifications, etc.
    """
    
    # Common section headers to look for in job descriptions
    SECTION_PATTERNS = {
        "responsibilities": [
            r"(?i)(responsibilities|what you'?ll do|duties|role|job duties|key responsibilities)",
            r"(?i)(you will|your role|your responsibilities|in this role)"
        ],
        "minimum_qualifications": [
            r"(?i)(minimum qualifications|basic qualifications|required qualifications|requirements|must have)",
            r"(?i)(required skills|minimum requirements|what we need|you have)"
        ],
        "preferred_qualifications": [
            r"(?i)(preferred qualifications|nice to have|bonus|preferred skills|desired|plus)",
            r"(?i)(ideal candidate|we'd love|preferred experience)"
        ],
        "about": [
            r"(?i)(about (the|this) (role|position|job)|job description|overview)",
            r"(?i)(position summary|role overview)"
        ]
    }
    
    def __init__(self, api_key: Optional[str] = None):
        openai_key = api_key or os.getenv("OPENAI_API_KEY")
        gemini_key = api_key or os.getenv("GEMINI_API_KEY")
        
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        if self.provider == "openai" and not openai_key:
            if gemini_key:
                self.provider = "gemini"
            else:
                raise ValueError("No LLM API keys found")
        
        if self.provider == "openai":
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=openai_key,
                temperature=0.3
            )
            self.gemini_model = None
        elif self.provider == "gemini":
            if not GEMINI_AVAILABLE:
                raise ValueError("google-generativeai package not available")
            genai.configure(api_key=gemini_key)
            self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
            self.llm = None
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    @staticmethod
    def _clean_html(html_text: str) -> str:
        """Remove HTML tags and clean up text."""
        # Remove script and style elements
        text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()
    
    def _extract_sections_by_pattern(self, text: str) -> Dict[str, str]:
        """Extract sections using regex patterns."""
        sections = {}
        
        for section_name, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    # Find the start position
                    start_pos = match.start()
                    
                    # Find the end position (next section or end of text)
                    # Look for next section header or take rest of text
                    rest_text = text[start_pos:]
                    
                    # Try to find where this section ends (next major header or 500 chars)
                    next_section_patterns = [
                        r'\n\s*(?:[A-Z][A-Za-z\s]{10,}:|\*\*[A-Z])',  # Next capitalized header
                        r'\n\s*(?:About|Requirements|Qualifications|Responsibilities|Benefits|Application)',
                    ]
                    
                    end_pos = len(rest_text)
                    for next_pattern in next_section_patterns:
                        next_match = re.search(next_pattern, rest_text[match.end()-start_pos:])
                        if next_match:
                            end_pos = match.end() - start_pos + next_match.start()
                            break
                    
                    # Extract section text (limit to reasonable length)
                    section_text = rest_text[:min(end_pos, 2000)].strip()
                    if section_text and len(section_text) > 20:
                        sections[section_name] = section_text
                        break  # Found this section, move to next
        
        return sections
    
    def extract_job_description(
        self,
        raw_text: str,
        company: Optional[str] = None,
        role: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Extract structured job description from raw text using LLM.
        
        Args:
            raw_text: Raw HTML or text from job page
            company: Company name (if known)
            role: Job title (if known)
            
        Returns:
            Dict with extracted fields: description, responsibilities, 
            minimum_qualifications, preferred_qualifications, etc.
        """
        # Clean the text
        clean_text = self._clean_html(raw_text)
        
        # Limit text length to avoid token limits
        if len(clean_text) > 8000:
            clean_text = clean_text[:8000] + "..."
        
        # First, try to extract sections using patterns
        extracted_sections = self._extract_sections_by_pattern(clean_text)
        
        # If we found sections, use them to build context
        if extracted_sections:
            context = "\n\n".join([
                f"**{key.replace('_', ' ').title()}:**\n{value}"
                for key, value in extracted_sections.items()
            ])
        else:
            context = clean_text
        
        # Use LLM to extract and structure the information
        template = """You are an expert at analyzing job descriptions.

Extract structured information from the job posting below. Focus on:
1. Main job description/overview
2. Key responsibilities (bullet points)
3. Minimum/required qualifications
4. Preferred qualifications (if mentioned)
5. Company information (if mentioned)

Job Posting Content:
{content}

{context_hint}

Provide a structured summary in this format:

**Job Overview:**
[2-3 sentence summary of the role]

**Key Responsibilities:**
- [Responsibility 1]
- [Responsibility 2]
- [etc.]

**Minimum Qualifications:**
- [Qualification 1]
- [Qualification 2]
- [etc.]

**Preferred Qualifications:**
- [Preferred skill 1]
- [Preferred skill 2]
- [etc., or "None specified" if not mentioned]

**About the Company/Role:**
[Any additional context about company or role]

Keep it concise and focus on the most important information.
"""
        
        context_hint = ""
        if company:
            context_hint += f"Company: {company}\n"
        if role:
            context_hint += f"Role: {role}\n"
        
        if self.provider == "openai":
            prompt = ChatPromptTemplate.from_template(template)
            chain = prompt | self.llm | StrOutputParser()
            
            try:
                result = chain.invoke({
                    "content": context[:6000],  # Limit to avoid token issues
                    "context_hint": context_hint
                })
            except Exception as e:
                print(f"[extractor] OpenAI extraction failed: {e}")
                raise
        elif self.provider == "gemini":
            prompt_text = template.format(
                content=context[:8000],
                context_hint=context_hint
            )
            try:
                response = self.gemini_model.generate_content(prompt_text)
                result = response.text or ""
            except Exception as e:
                print(f"[extractor] Gemini extraction failed: {e}")
                raise
        
        try:
            
            # Parse the result into a dict
            parsed = self._parse_llm_output(result)
            
            # Add the full extracted text as well
            parsed["raw_structured"] = result
            parsed["extracted_sections"] = extracted_sections
            
            return parsed
            
        except Exception as e:
            print(f"[extractor] LLM extraction failed: {e}")
            # Return basic extracted sections if LLM fails
            return {
                "description": extracted_sections.get("about", clean_text[:500]),
                "responsibilities": extracted_sections.get("responsibilities", ""),
                "minimum_qualifications": extracted_sections.get("minimum_qualifications", ""),
                "preferred_qualifications": extracted_sections.get("preferred_qualifications", ""),
                "extracted_sections": extracted_sections
            }
    
    def _parse_llm_output(self, output: str) -> Dict[str, str]:
        """Parse the structured LLM output into a dictionary."""
        sections = {
            "description": "",
            "responsibilities": "",
            "minimum_qualifications": "",
            "preferred_qualifications": "",
            "about_company": ""
        }
        
        # Extract each section using markers
        patterns = {
            "description": r"\*\*Job Overview:\*\*\s*(.*?)(?=\*\*|$)",
            "responsibilities": r"\*\*Key Responsibilities:\*\*\s*(.*?)(?=\*\*|$)",
            "minimum_qualifications": r"\*\*Minimum Qualifications:\*\*\s*(.*?)(?=\*\*|$)",
            "preferred_qualifications": r"\*\*Preferred Qualifications:\*\*\s*(.*?)(?=\*\*|$)",
            "about_company": r"\*\*About the Company/Role:\*\*\s*(.*?)(?=\*\*|$)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
            if match:
                sections[key] = match.group(1).strip()
        
        # Combine into a single description if needed
        if not sections["description"] and sections["responsibilities"]:
            sections["description"] = f"{sections['responsibilities']}\n\n{sections['minimum_qualifications']}"
        
        return sections


def extract_job_info(
    html_or_text: str,
    company: Optional[str] = None,
    role: Optional[str] = None,
    openai_api_key: Optional[str] = None
) -> Dict[str, str]:
    """
    Convenience function to extract job information.
    
    Args:
        html_or_text: Raw HTML or text from job page
        company: Company name (optional)
        role: Job title (optional)
        openai_api_key: OpenAI API key (optional, uses env var if not provided)
        
    Returns:
        Dict with structured job information
    """
    try:
        extractor = JobDescriptionExtractor(openai_api_key)
        return extractor.extract_job_description(html_or_text, company, role)
    except Exception as e:
        print(f"[extractor] Failed to initialize: {e}")
        return {
            "description": html_or_text[:1000] if html_or_text else "",
            "error": str(e)
        }

