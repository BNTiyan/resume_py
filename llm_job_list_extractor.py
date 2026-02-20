"""
LLM-based job list extractor for parsing career pages with multiple job listings.
Extracts job URLs, titles, locations, and descriptions from HTML using LLM.
"""
import os
import re
import html
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

from langchain_core.prompts import ChatPromptTemplate
# We use LLMManager to get the client, but we might need to wrap it 
# or just use the generate method directly. 
# For simplicity, we will use the LLMManager's generate method.
from llm_manager import get_llm

class LLMJobListExtractor:
    """
    Extract multiple job listings from a career page HTML using LLM.
    More robust than CSS selectors - can adapt to different page structures.
    Uses LLMManager to support multiple providers (Gemini, Ollama, OpenAI).
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.llm_manager = get_llm()
        # Ensure LLM is initialized
        if not self.llm_manager.client:
            # Try to initialize with provided config if not already ready
            if config:
                self.llm_manager.config = config
                self.llm_manager._initialize()
    
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
        """
        # First, extract all links from HTML
        all_links = self._extract_links_from_html(html_content, base_url)
        
        # Extract links text for context
        links_text = "\n".join([
            f"Link: {link['url']} | Text: {link['text'][:120]}"
            for link in all_links[:300]  # up to 300 links
        ])

        # Provide a tiny HTML snippet (headings/titles only) for extra context.
        cleaned_snippet = self._clean_html(html_content)[:3000]

        # Build prompt for LLM
        system_msg = """You are an expert at identifying job listings from career page link lists.

Instructions:
1. From the provided links, identify those that point to individual job postings.
2. For each job link extract:
   - Job title (from link text or nearby context)
   - Job URL (absolute)
   - Location (if visible in link text, else "")
   - Brief description (max 100 chars, else "")

3. Return ONLY a JSON array:
[
  {
    "title": "Job Title",
    "url": "https://full-url-to-job-posting",
    "location": "City, State or Remote",
    "description": "Brief job description"
  }
]

RULES:
- Skip navigation links ("Learn More", "About Us", "Home", etc.)
- URLs must be absolute (http:// or https://)
- Max {max_jobs} jobs
- Return [] if no jobs found
- Output ONLY valid JSON, no markdown formatting.
"""

        user_msg = f"""**Company:** {company}
**Base URL:** {base_url}

**All links found on the page (url | link text):**
{links_text}

**Page heading context (first 3k chars of visible text):**
{cleaned_snippet}
"""

        messages = [
            {"role": "system", "content": system_msg.replace("{max_jobs}", str(max_jobs))},
            {"role": "user", "content": user_msg}
        ]

        try:
            # Use LLMManager to generate response
            response = self.llm_manager.generate(messages, temperature=0.1, max_tokens=4000)
            
            # Parse JSON response
            response = response.strip()
            
            # Remove markdown code blocks if present
            if "```" in response:
                response = re.sub(r'^```(?:json)?\s*', '', response)
                response = re.sub(r'\s*```$', '', response)
            
            # Try to extract JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                jobs = json.loads(json_match.group(0))
            else:
                # Try parsing entire response as JSON
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
    openai_api_key: Optional[str] = None, # kept for signature compat, but ignored/deprecated
    max_jobs: int = 50
) -> List[Dict[str, str]]:
    """
    Convenience function to extract jobs from HTML.
    
    Args:
        html_content: Raw HTML from career page
        base_url: Base URL for resolving relative links
        company: Company name (optional)
        openai_api_key: DEPRECATED - used to be for OpenAI, now usage is delegated to LLMManager
        max_jobs: Maximum number of jobs to extract
        
    Returns:
        List of job dicts
    """
    try:
        # LLMManager handles keys via env vars or internal config
        extractor = LLMJobListExtractor()
        return extractor.extract_jobs_from_html(html_content, base_url, company, max_jobs)
    except Exception as e:
        print(f"[llm-extractor] Failed to initialize: {e}")
        return []

