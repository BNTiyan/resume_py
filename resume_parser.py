"""
Resume Parsing Utilities

Turn an uploaded resume (PDF/DOCX/TXT) into structured JSON:
- basics: name, email, phone, links
- skills: list of skills (best-effort)
- raw_sections: text chunks for work experience, education, projects

This is a lightweight, ATS-style parser that does NOT require an LLM.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from docx import Document as DocxDocument
from PyPDF2 import PdfReader


EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")
URL_RE = re.compile(r"https?://[^\s,;]+", re.IGNORECASE)


def extract_text_from_file(path: Path) -> str:
    """Extract plain text from a resume file (PDF, DOCX, or TXT)."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        try:
            reader = PdfReader(str(path))
            texts: List[str] = []
            for page in reader.pages:
                try:
                    texts.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n".join(texts).strip()
        except Exception as e:
            print(f"[parser] Failed to extract text from PDF: {e}")
            return ""

    if suffix == ".docx":
        try:
            doc = DocxDocument(str(path))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as e:
            print(f"[parser] Failed to extract text from DOCX: {e}")
            return ""

    if suffix in {".txt", ".md"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"[parser] Failed to read text file: {e}")
            return ""

    print(f"[parser] Unsupported file type for parsing: {suffix}")
    return ""


def _guess_name(lines: List[str]) -> str:
    """Heuristic: first non-empty line that looks like a name."""
    for line in lines[:20]:
        s = line.strip()
        if not s:
            continue
        if "@" in s or "|" in s or s.lower().startswith(("resume", "curriculum", "cv ")):
            continue
        if len(s) > 60:
            continue
        # Simple "looks like a name" heuristic: 2–4 words, capitalized
        parts = s.split()
        if 1 <= len(parts) <= 4 and all(p[0].isupper() for p in parts if p):
            return s
    return ""


def _extract_basics(text: str) -> Dict[str, Any]:
    lines = text.splitlines()
    basics: Dict[str, Any] = {}

    basics["name"] = _guess_name(lines)

    emails = EMAIL_RE.findall(text)
    basics["email"] = emails[0] if emails else ""

    phones = PHONE_RE.findall(text)
    basics["phone"] = phones[0].strip() if phones else ""

    urls = URL_RE.findall(text)
    linkedin = ""
    github = ""
    others: List[str] = []
    for u in urls:
        lu = u.lower()
        if "linkedin.com" in lu and not linkedin:
            linkedin = u
        elif "github.com" in lu and not github:
            github = u
        else:
            others.append(u)

    basics["linkedin"] = linkedin
    basics["github"] = github
    basics["urls"] = others
    return basics


def _extract_skills(text: str) -> List[str]:
    """Best-effort skills extraction from a 'Skills' section."""
    lines = text.splitlines()
    skills_block: List[str] = []
    in_skills = False

    for line in lines:
        l = line.strip()
        lower = l.lower()
        if not in_skills:
            if lower.startswith("skills") or "technical skills" in lower or "key skills" in lower:
                in_skills = True
                # capture part after colon, if present
                if ":" in l:
                    skills_block.append(l.split(":", 1)[1])
                continue
        else:
            if not l:
                break
            if lower.endswith(":") or lower in {"experience", "work experience", "education", "projects"}:
                break
            skills_block.append(l)

    if not skills_block:
        return []

    raw = " ".join(skills_block)
    # Split on commas / pipes / semicolons
    parts = re.split(r"[,\|;/]", raw)
    skills = sorted({p.strip() for p in parts if p.strip()})
    return skills


def _extract_section(text: str, section_names: List[str]) -> str:
    """Extract a rough text block for a given section (e.g., experience)."""
    lines = text.splitlines()
    current: List[str] = []
    capture = False
    # Look for section headers (at start of line, optionally followed by colon or separator)
    pattern = r"^\s*(" + "|".join(re.escape(s) for s in section_names) + r")[:\s]*$"
    section_re = re.compile(pattern, re.IGNORECASE)
    
    # Sections that typically signal the end of the current one
    stop_patterns = ["skills", "projects", "education", "experience", "summary", "profile", "certifications", "achievements"]
    stop_re = re.compile(r"^\s*(" + "|".join(stop_patterns) + r")[:\s]*$", re.IGNORECASE)

    for line in lines:
        l = line.strip()
        if not l:
            if capture:
                current.append(line)
            continue
            
        if not capture and section_re.search(l):
            capture = True
            continue
        
        if capture:
            # If we hit another section header, stop
            if stop_re.search(l) and not section_re.search(l):
                break
            current.append(line)

    return "\n".join(current).strip()


def parse_resume_text(text: str) -> Dict[str, Any]:
    """
    Core parser: takes raw resume text and returns structured JSON.

    This is intentionally deterministic / regex-based so it can run on
    cheap/free infrastructure without any LLM.
    """
    if not text:
        return {"basics": {}, "skills": [], "raw_sections": {}}

    raw_summary = _extract_section(text, ["summary", "professional summary", "profile", "executive summary", "objective"])
    if raw_summary:
        # Split into list of sentences/lines if it looks like paragraphs
        summary_points = [p.strip() for p in re.split(r'\n|\. ', raw_summary) if p.strip()]
        basics["summary"] = summary_points

    raw_sections = {
        "experience": _extract_section(text, ["experience", "work experience", "professional experience"]),
        "education": _extract_section(text, ["education", "academic background"]),
        "projects": _extract_section(text, ["projects", "personal projects", "key projects"]),
    }

    return {
        "basics": basics,
        "skills": skills,
        "raw_sections": raw_sections,
        "summary_char_count": len(text),
    }


def parse_resume_file(path: Path) -> Dict[str, Any]:
    """Convenience: extract text from a file and parse it into JSON."""
    text = extract_text_from_file(path)
    return parse_resume_text(text)


