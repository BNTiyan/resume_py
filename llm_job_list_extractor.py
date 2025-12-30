"""
LLM-based job list extractor for parsing career pages with multiple job listings.
Extracts job URLs, titles, locations, and descriptions from HTML using LLM.
"""
import os
import re
import html
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

try:
    import openai_compat  # noqa: F401
except Exception:
    openai_compat = None

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class LLMJobListExtractor:
    """
    Extract multiple job listings from a career page HTML using LLM.
    More robust than CSS selectors - can adapt to different page structures.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required")
        
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=api_key,
            temperature=0.1  # Low temperature for consistent extraction
        )
        self.output_parser = StrOutputParser()
    
    @staticmethod
    def _clean_html(html_text: str) -> str:
        """Remove HTML tags and clean up text, but preserve structure."""
        # Remove script and style tags
        html_text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', '', html_text)
        
        # Replace common HTML entities
        html_text = html_text.replace('&nbsp;', ' ')
        html_text = html_text.replace('&amp;', '&')
        html_text = html_text.replace('&lt;', '<')
        html_text = html_text.replace('&gt;', '>')
        html_text = html_text.replace('&quot;', '"')
        
        # Remove HTML tags but keep text content
        html_text = re.sub(r'<[^>]+>', ' ', html_text)
        
        # Clean up whitespace
        html_text = re.sub(r'\s+', ' ', html_text)
        html_text = html_text.strip()
        
        return html_text
    
    @staticmethod
    def _extract_links_from_html(html_text: str, base_url: str) -> List[Dict[str, str]]:
        """Extract all links from HTML using regex."""
        links = []
        # Find all <a> tags with href attributes
        pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        matches = re.finditer(pattern, html_text, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            href = html.unescape(match.group(1))
            text = html.unescape(re.sub(r'<[^>]+>', '', match.group(2))).strip()
            
            # Normalize relative URLs
            if href.startswith('/'):
                href = urljoin(base_url, href)
            elif not href.startswith('http'):
                href = urljoin(base_url, '/' + href)
            
            links.append({
                "url": href,
                "text": text
            })
        
        return links
    
    def extract_jobs_from_html(
        self,
        html_content: str,
        base_url: str,
        company: Optional[str] = None,
        max_jobs: int = 50
    ) -> List[Dict[str, str]]:
        """
        Extract job listings from HTML using LLM.
        
        Args:
            html_content: Raw HTML from career page
            base_url: Base URL for resolving relative links
            company: Company name (if known)
            max_jobs: Maximum number of jobs to extract
            
        Returns:
            List of job dicts with: title, company, location, url, description
        """
        # First, extract all links from HTML
        all_links = self._extract_links_from_html(html_content, base_url)
        
        # Clean HTML for LLM processing (limit size)
        cleaned_html = self._clean_html(html_content)
        if len(cleaned_html) > 30000:  # Limit to ~30k chars
            cleaned_html = cleaned_html[:30000] + "..."
        
        # Extract links text for context
        links_text = "\n".join([
            f"Link: {link['url']} | Text: {link['text'][:100]}"
            for link in all_links[:200]  # Limit to first 200 links
        ])
        
        # Build prompt for LLM
        prompt_template = ChatPromptTemplate.from_template("""
You are an expert at extracting job listings from career pages. Analyze the HTML content and links below to extract all job postings.

**Company:** {company}
**Base URL:** {base_url}

**Available Links:**
{links_text}

**Page Content (first 30k chars):**
{cleaned_html}

**Instructions:**
1. Identify all job postings on this page
2. For each job, extract:
   - Job title
   - Job URL (must be a valid absolute URL)
   - Location (if available)
   - Brief description (if available, max 200 chars)

3. Return results in this EXACT JSON format (array of objects):
[
  {{
    "title": "Job Title",
    "url": "https://full-url-to-job-posting",
    "location": "City, State or Remote",
    "description": "Brief job description"
  }},
  ...
]

**CRITICAL RULES:**
- Only include jobs (not "Learn More", "About Us", etc.)
- URLs MUST be absolute (start with http:// or https://)
- URLs should point to individual job detail pages, not general pages
- If URL is relative, make it absolute using base_url
- Extract at most {max_jobs} jobs
- If you can't find any jobs, return an empty array: []

**Output ONLY valid JSON, no other text:**
""")
        
        try:
            chain = prompt_template | self.llm | self.output_parser
            response = chain.invoke({
                "company": company or "Unknown",
                "base_url": base_url,
                "links_text": links_text[:5000],  # Limit links text
                "cleaned_html": cleaned_html,
                "max_jobs": max_jobs
            })
            
            # Parse JSON response
            response = response.strip()
            
            # Remove markdown code blocks if present
            if response.startswith("```"):
                response = re.sub(r'^```(?:json)?\s*', '', response)
                response = re.sub(r'\s*```$', '', response)
            
            # Try to extract JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                import json
                jobs = json.loads(json_match.group(0))
            else:
                # Try parsing entire response as JSON
                import json
                jobs = json.loads(response)
            
            # Validate and normalize jobs
            validated_jobs = []
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                
                title = (job.get("title") or "").strip()
                url = (job.get("url") or "").strip()
                
                # Skip if no title or URL
                if not title or not url:
                    continue
                
                # Ensure URL is absolute
                if url.startswith('/'):
                    url = urljoin(base_url, url)
                elif not url.startswith('http'):
                    url = urljoin(base_url, '/' + url)
                
                validated_jobs.append({
                    "title": title,
                    "company": company or "",
                    "location": (job.get("location") or "").strip(),
                    "description": (job.get("description") or "").strip()[:500],
                    "url": url,
                    "source": f"llm_extractor:{company or 'unknown'}"
                })
            
            print(f"[llm-extractor] Extracted {len(validated_jobs)} jobs from {company or 'unknown'} page")
            return validated_jobs[:max_jobs]
            
        except Exception as e:
            print(f"[llm-extractor] Error extracting jobs: {type(e).__name__}: {e}")
            import traceback
            print(f"[llm-extractor] Traceback: {traceback.format_exc()[:300]}")
            return []


def extract_jobs_from_html(
    html_content: str,
    base_url: str,
    company: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    max_jobs: int = 50
) -> List[Dict[str, str]]:
    """
    Convenience function to extract jobs from HTML.
    
    Args:
        html_content: Raw HTML from career page
        base_url: Base URL for resolving relative links
        company: Company name (optional)
        openai_api_key: OpenAI API key (optional, uses env var if not provided)
        max_jobs: Maximum number of jobs to extract
        
    Returns:
        List of job dicts
    """
    try:
        extractor = LLMJobListExtractor(openai_api_key)
        return extractor.extract_jobs_from_html(html_content, base_url, company, max_jobs)
    except Exception as e:
        print(f"[llm-extractor] Failed to initialize: {e}")
        return []

