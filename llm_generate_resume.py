"""
Self-contained LangChain-powered resume generator.

This class mirrors the intent of the upstream `LLMResumer` while avoiding
external package dependencies.  It parses a plain-text resume, derives
structured sections, and uses OpenAI chat models (via LangChain) to create
ATS-friendly tailored resumes and cover letters.
"""

import os
import re
import textwrap
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import openai_compat  # noqa: F401
except Exception:
    openai_compat = None

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

load_dotenv()

# Configure log file
LOG_FOLDER = "log/resume/llm_resumer"
os.makedirs(LOG_FOLDER, exist_ok=True)
_LOG_PATH = Path(LOG_FOLDER).resolve()
logger.add(
    _LOG_PATH / "llm_resumer.log",
    rotation="1 day",
    compression="zip",
    retention="7 days",
    level="DEBUG",
)


_STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "about",
    "your",
    "their",
    "have",
    "will",
    "able",
    "using",
    "based",
    "team",
    "work",
    "role",
    "company",
    "skills",
    "experience",
}  # keep domain-specific keywords (e.g., PYTHON) available for weighting


SECTION_ALIASES: Dict[str, tuple[str, ...]] = {
    "summary": (
        "SUMMARY",
        "PROFESSIONAL SUMMARY",
        "SUMMARY OF QUALIFICATIONS",
        "PROFILE",
        "OBJECTIVE",
        "ABOUT",
        "CAREER SUMMARY",
    ),
    "experience_details": (
        "WORK EXPERIENCE",
        "PROFESSIONAL EXPERIENCE",
        "EXPERIENCE",
        "EMPLOYMENT",
        "EMPLOYMENT HISTORY",
        "RELEVANT EXPERIENCE",
        "VOLUNTEER EXPERIENCE",
    ),
    "education_details": (
        "EDUCATION",
        "ACADEMIC BACKGROUND",
        "ACADEMICS",
        "HIGHER EDUCATION",
    ),
    "projects": (
        "PROJECTS",
        "TECHNICAL PROJECTS",
        "PERSONAL PROJECTS",
        "SELECTED PROJECTS",
        "OPEN SOURCE",
    ),
    "achievements": (
        "ACHIEVEMENTS",
        "AWARDS",
        "HONORS",
        "RECOGNITION",
        "PUBLICATIONS",
        "EXTRACURRICULAR",
    ),
    "certifications": (
        "CERTIFICATIONS",
        "CERTIFICATION",
        "CERTIFICATES",
        "LICENSES",
    ),
    "skills": (
        "SKILLS",
        "TECHNICAL SKILLS",
        "TECHNOLOGIES",
        "TOOLS",
        "CORE COMPETENCIES",
        "STACK",
    ),
    "languages": ("LANGUAGES",),
    "interests": ("INTERESTS", "HOBBIES", "PASSIONS"),
    "additional_notes": (
        "ADDITIONAL INFORMATION",
        "ADDITIONAL DETAILS",
        "OTHER",
    ),
}


@dataclass
class ResumeSections:
    personal_information: str = ""
    summary: str = ""
    experience_details: str = ""
    education_details: str = ""
    projects: str = ""
    achievements: str = ""
    certifications: str = ""
    skills: str = ""
    interests: str = ""
    languages: str = ""
    additional_notes: str = ""

    def as_dict(self) -> Dict[str, str]:
        return {
            "personal_information": self.personal_information,
            "summary": self.summary,
            "experience_details": self.experience_details,
            "education_details": self.education_details,
            "projects": self.projects,
            "achievements": self.achievements,
            "certifications": self.certifications,
            "skills": self.skills,
            "interests": self.interests,
            "languages": self.languages,
            "additional_notes": self.additional_notes,
        }


@dataclass
class ResumePromptLibrary:
    job_summary: str
    header: str
    summary: str
    experience: str
    education: str
    projects: str
    achievements: str
    certifications: str
    additional_skills: str
    cover_letter: str

    @classmethod
    def default(cls) -> "ResumePromptLibrary":
        return cls(
            job_summary=textwrap.dedent(
                """
                You are an expert hiring analyst.

                Read the job description carefully and extract the essentials:
                - Mission or business impact of the role
                - Top responsibilities (3-5 bullets)
                - Required technical skills or tools
                - Preferred or nice-to-have experience
                - Cultural notes, team style, or success metrics

                Job description:
                {text}

                Respond with concise bullet points starting with "- ".
                """
            ),
            header=textwrap.dedent(
                """
                You are customizing the contact block for a technical resume.

                Company: {company}
                Role: {role}

                Candidate contact lines:
                {personal_information}

                Branding summary lines:
                {summary}

                Resume keywords to preserve:
                {resume_keywords}

                Job focus summary:
                {job_summary}

                Instructions:
                1. First line: candidate name in Title Case (infer from contact lines).
                2. Second line: location and contact channels separated by " | " (only include available fields).
                3. Third line: concise branding sentence that links the candidate to the target role.
                4. Keep plain text with exactly three lines.
                """
            ),
            summary=textwrap.dedent(
                """
                You are writing the SUMMARY section of a resume tailored to {role} at {company}.

                Existing statement:
                {summary}

                Experience snippets:
                {experience_details}

                Notable achievements:
                {achievements}

                Job summary:
                {job_summary}

                High-priority keywords:
                {job_keywords}

                Produce a SUMMARY section with the heading "SUMMARY" followed by three bullet points (use the "•" bullet).
                Each bullet must be under 28 words, highlight quantifiable impact, and reference relevant tools or skills.
                """
            ),
            experience=textwrap.dedent(
                """
                Craft the WORK EXPERIENCE section for a candidate applying to {role} at {company}.

                Candidate's original experience:
                {experience_details}

                Job description summary:
                {job_summary}

                Keywords to emphasize:
                {job_keywords}

                Resume keywords to retain:
                {resume_keywords}

                Rules:
                - Keep roles in reverse chronological order.
                - For each role, include "Company – Title | Location | Dates" on one line.
                - Add 3-4 bullet points per role, each starting with "•" and containing a measurable result.
                - Mention technologies and scale when available.

                Output should start with the heading "WORK EXPERIENCE".
                """
            ),
            education=textwrap.dedent(
                """
                Draft the EDUCATION section for the resume.

                Candidate education details:
                {education_details}

                Job summary:
                {job_summary}

                Requirements:
                - Start with "EDUCATION".
                - Present each entry as "Degree — Institution, Location (Dates)".
                - Add one supporting line per entry with GPA, coursework, or achievements when relevant.
                - Align emphasis with the job summary when possible.
                """
            ),
            projects=textwrap.dedent(
                """
                Prepare the PROJECTS section for an ATS-optimized resume for {role} at {company}.

                Candidate project details:
                {projects}

                Job summary:
                {job_summary}

                Keywords to inject:
                {job_keywords}

                Format instructions:
                - Begin with "PROJECTS".
                - Each project line: "Project Name — Tech Stack | Link (if available)".
                - Provide 1-2 bullets beneath each project focusing on impact, scale, and technologies.
                - Use "•" for bullets.
                """
            ),
            achievements=textwrap.dedent(
                """
                Compile the ACHIEVEMENTS section.

                Existing achievements:
                {achievements}

                Job summary:
                {job_summary}

                Guideline:
                - Start with "ACHIEVEMENTS".
                - Each bullet (prefixed with "•") should describe the recognition and its relevance to the target role.
                """
            ),
            certifications=textwrap.dedent(
                """
                Build the CERTIFICATIONS section using the candidate data.

                Certifications list:
                {certifications}

                Job summary:
                {job_summary}

                Output format:
                - Heading "CERTIFICATIONS".
                - One line per certification: "Certification — Issuer (Year) — Relevance".
                """
            ),
            additional_skills=textwrap.dedent(
                """
                Craft the ADDITIONAL SKILLS section to align with the role {role} at {company}.

                Skills inventory:
                {skills}

                Languages:
                {languages}

                Interests:
                {interests}

                Additional notes:
                {additional_notes}

                Resume keywords to keep:
                {resume_keywords}

                Job keywords to prioritize:
                {job_keywords}

                Output:
                - Heading "ADDITIONAL SKILLS".
                - Group related skills or tools, using "•" bullets or concise comma-separated phrases.
                - Highlight language proficiency and any relevant interests at the end.
                """
            ),
            cover_letter=textwrap.dedent(
                """
                You are writing a cover letter body (no greeting or signature) for a candidate applying to {role} at {company}.

                Job summary:
                {job_summary}

                Resume context (abridged):
                {resume_text}

                Key experience bullets:
                {experience_bullets}

                Project highlights:
                {project_highlights}

                Instructions:
                - Write 3 paragraphs (opening, core value proposition, closing call-to-action).
                - Reference 2-3 concrete achievements from the resume.
                - Mirror terminology from the job summary.
                - Tone: professional, confident, and specific to the company.
                - No greeting or signature.
                """
            ),
        )


class LLMResumer:
    """
    Generate tailored resumes (and optionally cover letters) using LangChain + OpenAI.

    Workflow:
    1. Call `set_resume_data()` with the base resume text.
    2. Invoke `generate_tailored_resume()` and/or `generate_cover_letter()` with job details.
    3. Optionally call `generate_resume_and_cover_letter()` for parallel generation.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        strings: Optional[Any] = None,
        *,
        model: str = "gpt-4o-mini",
        temperature: float = 0.35,
        provider: Optional[str] = None,
    ) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        openai_key = api_key if self.provider == "openai" else os.getenv("OPENAI_API_KEY")
        gemini_key = api_key if self.provider == "gemini" else os.getenv("GEMINI_API_KEY")

        if self.provider == "openai" and not openai_key:
            if gemini_key:
                self.provider = "gemini"
            else:
                raise ValueError("OpenAI API key required")
        
        if self.provider == "gemini" and not gemini_key:
            raise ValueError("Gemini API key required")

        self.model = model
        self.temperature = temperature
        
        if self.provider == "openai":
            self.llm_resume = ChatOpenAI(
                model=model,
                api_key=openai_key,
                temperature=temperature,
            )
            self.llm_cover = ChatOpenAI(
                model=model,
                api_key=openai_key,
                temperature=0.45,
            )
        else:
            gemini_model = os.getenv("GEMINI_RESUME_MODEL", "gemini-1.5-flash")
            self.llm_resume = ChatGoogleGenerativeAI(
                model=gemini_model,
                google_api_key=gemini_key,
                temperature=temperature,
            )
            self.llm_cover = ChatGoogleGenerativeAI(
                model=gemini_model,
                google_api_key=gemini_key,
                temperature=0.45,
            )

        self.strings = self._coerce_strings(strings)
        self.resume_text: str = ""
        self.resume_sections = ResumeSections()
        self.resume_keywords: List[str] = []
        self.job_keywords: List[str] = []
        self._resume_context: Dict[str, str] = {}
        logger.debug("LLMResumer initialized with model {}", model)

    @staticmethod
    def _coerce_strings(strings: Optional[Any]) -> ResumePromptLibrary:
        default_prompts = ResumePromptLibrary.default()
        if isinstance(strings, ResumePromptLibrary):
            return strings
        if strings:
            # Support legacy objects with prompt_* attributes
            return ResumePromptLibrary(
                job_summary=getattr(strings, "summarize_prompt_template", None)
                or getattr(strings, "job_summary", default_prompts.job_summary),
                header=getattr(strings, "prompt_header", default_prompts.header),
                summary=getattr(strings, "prompt_summary", default_prompts.summary),
                experience=getattr(
                    strings,
                    "prompt_working_experience",
                    default_prompts.experience,
                ),
                education=getattr(strings, "prompt_education", default_prompts.education),
                projects=getattr(strings, "prompt_projects", default_prompts.projects),
                achievements=getattr(
                    strings,
                    "prompt_achievements",
                    default_prompts.achievements,
                ),
                certifications=getattr(
                    strings,
                    "prompt_certifications",
                    default_prompts.certifications,
                ),
                additional_skills=getattr(
                    strings,
                    "prompt_additional_skills",
                    default_prompts.additional_skills,
                ),
                cover_letter=getattr(
                    strings,
                    "prompt_cover_letter",
                    default_prompts.cover_letter,
                ),
            )
        return default_prompts

    def set_resume(self, resume: ResumeSections) -> None:
        """Backward-compatible helper retained for older integrations."""
        self.resume_sections = resume
        self.resume_text = "\n".join(
            value for value in resume.as_dict().values() if value
        )
        self.resume_keywords = self._extract_keywords(self.resume_text)
        self._resume_context = self._build_resume_context()

    def set_resume_data(self, resume_text: str) -> None:
        """
        Parse raw resume text into structured sections and prepare context.
        """
        if not resume_text or not resume_text.strip():
            raise ValueError("Resume text cannot be empty")

        self.resume_text = resume_text.strip()
        self.resume_sections = self._parse_resume_sections(self.resume_text)
        self.resume_keywords = self._extract_keywords(self.resume_text, limit=28)
        self._resume_context = self._build_resume_context()
        logger.debug(
            "Loaded resume with sections: {}", [k for k, v in self.resume_sections.as_dict().items() if v]
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #
    def _ensure_resume_loaded(self) -> None:
        if not self.resume_text:
            raise RuntimeError(
                "Resume not set. Call set_resume_data() before generating content."
            )

    def _identify_section(self, line: str) -> Optional[str]:
        cleaned = re.sub(r"[^A-Z0-9 ]", " ", line.upper()).strip()
        for section, aliases in SECTION_ALIASES.items():
            for alias in aliases:
                if cleaned == alias or cleaned.startswith(alias) or alias in cleaned:
                    return section
        return None

    def _parse_resume_sections(self, resume_text: str) -> ResumeSections:
        lines = [ln.rstrip() for ln in resume_text.splitlines()]
        section_buffers: Dict[str, List[str]] = {
            "summary": [],
            "experience_details": [],
            "education_details": [],
            "projects": [],
            "achievements": [],
            "certifications": [],
            "skills": [],
            "languages": [],
            "interests": [],
            "additional_notes": [],
        }
        personal_lines: List[str] = []
        current_section = "summary"
        header_captured = False

        for raw in lines:
            stripped = raw.strip()
            if not stripped:
                if personal_lines and not header_captured:
                    header_captured = True
                continue

            maybe_section = self._identify_section(stripped)
            if maybe_section:
                current_section = maybe_section
                header_captured = True
                continue

            if not header_captured:
                personal_lines.append(stripped)
            else:
                section_buffers[current_section].append(stripped)

        return ResumeSections(
            personal_information="\n".join(personal_lines).strip(),
            summary="\n".join(section_buffers["summary"]).strip(),
            experience_details="\n".join(section_buffers["experience_details"]).strip(),
            education_details="\n".join(section_buffers["education_details"]).strip(),
            projects="\n".join(section_buffers["projects"]).strip(),
            achievements="\n".join(section_buffers["achievements"]).strip(),
            certifications="\n".join(section_buffers["certifications"]).strip(),
            skills="\n".join(section_buffers["skills"]).strip(),
            interests="\n".join(section_buffers["interests"]).strip(),
            languages="\n".join(section_buffers["languages"]).strip(),
            additional_notes="\n".join(section_buffers["additional_notes"]).strip(),
        )

    @staticmethod
    def _extract_keywords(text: str, limit: int = 25) -> List[str]:
        if not text:
            return []
        tokens = re.findall(r"[A-Za-z0-9+#.\-/]+", text.lower())
        filtered = [tok for tok in tokens if len(tok) > 2 and tok not in _STOPWORDS]
        if not filtered:
            return []
        counts = Counter(filtered)
        return [word.upper() for word, _ in counts.most_common(limit)]

    @staticmethod
    def _extract_bullets(text: str, limit: int = 12) -> List[str]:
        bullets: List[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            stripped = re.sub(r"^[•\-\*\u2022]+\s*", "", stripped)
            if stripped:
                bullets.append(stripped)
            if len(bullets) >= limit:
                break
        return bullets

    def _build_resume_context(self) -> Dict[str, str]:
        sections = self.resume_sections.as_dict()
        context = {key: (value or "") for key, value in sections.items()}
        context["resume_text"] = self.resume_text
        context["resume_keywords"] = ", ".join(self.resume_keywords[:24])
        context["experience_bullets"] = "\n".join(
            self._extract_bullets(self.resume_sections.experience_details, limit=10)
        )
        context["project_highlights"] = "\n".join(
            self._extract_bullets(self.resume_sections.projects, limit=6)
        )
        # Default placeholders for job-specific fields (overridable later)
        context.setdefault("job_summary", "")
        context.setdefault("job_description", "")
        context.setdefault("job_keywords", "")
        context.setdefault("company", "")
        context.setdefault("role", "")
        return context

    def _summarize_job_description(self, job_description: str) -> str:
        text = (job_description or "").strip()
        if not text:
            return ""
        prompt = ChatPromptTemplate.from_template(self.strings.job_summary)
        chain = prompt | self.llm_resume | StrOutputParser()
        summary = chain.invoke({"text": text})
        logger.debug("Generated job summary ({} chars)", len(summary))
        return summary.strip()

    def _prepare_job_excerpt(self, job_description: str, max_chars: int = 4000) -> str:
        clean = textwrap.dedent(job_description or "").strip()
        if not clean:
            self.job_keywords = []
            return ""
        truncated = clean[:max_chars]
        if len(clean) > max_chars:
            truncated = clean[:max_chars] + "..."
        self.job_keywords = self._extract_keywords(clean, limit=22)
        return truncated

    def _build_job_context(
        self,
        job_description: str,
        company: str,
        role: str,
        job_summary: Optional[str] = None,
    ) -> Dict[str, str]:
        summary = job_summary or self._summarize_job_description(job_description)
        excerpt = self._prepare_job_excerpt(job_description)
        return {
            "job_summary": summary,
            "job_description": excerpt,
            "company": company,
            "role": role,
            "job_keywords": ", ".join(self.job_keywords[:20]),
        }

    def _invoke_prompt(
        self,
        template: str,
        context: Dict[str, Any],
        *,
        llm: Optional[ChatOpenAI] = None,
    ) -> str:
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | (llm or self.llm_resume) | StrOutputParser()
        result = chain.invoke(context)
        return (result or "").strip()

    # ------------------------------------------------------------------ #
    # Section generators                                                 #
    # ------------------------------------------------------------------ #
    def generate_header(self, data: Optional[Dict[str, Any]] = None) -> str:
        context = dict(self._resume_context)
        if data:
            context.update(data)
        return self._invoke_prompt(self.strings.header, context)

    def generate_summary_section(self, data: Optional[Dict[str, Any]] = None) -> str:
        context = dict(self._resume_context)
        if data:
            context.update(data)
        return self._invoke_prompt(self.strings.summary, context)

    def generate_work_experience_section(
        self, data: Optional[Dict[str, Any]] = None
    ) -> str:
        context = dict(self._resume_context)
        if data:
            context.update(data)
        return self._invoke_prompt(self.strings.experience, context)

    def generate_education_section(self, data: Optional[Dict[str, Any]] = None) -> str:
        context = dict(self._resume_context)
        if data:
            context.update(data)
        return self._invoke_prompt(self.strings.education, context)

    def generate_projects_section(self, data: Optional[Dict[str, Any]] = None) -> str:
        context = dict(self._resume_context)
        if data:
            context.update(data)
        return self._invoke_prompt(self.strings.projects, context)

    def generate_achievements_section(
        self, data: Optional[Dict[str, Any]] = None
    ) -> str:
        context = dict(self._resume_context)
        if data:
            context.update(data)
        return self._invoke_prompt(self.strings.achievements, context)

    def generate_certifications_section(
        self, data: Optional[Dict[str, Any]] = None
    ) -> str:
        context = dict(self._resume_context)
        if data:
            context.update(data)
        return self._invoke_prompt(self.strings.certifications, context)

    def generate_additional_skills_section(
        self, data: Optional[Dict[str, Any]] = None
    ) -> str:
        context = dict(self._resume_context)
        if data:
            context.update(data)
        return self._invoke_prompt(self.strings.additional_skills, context)

    # ------------------------------------------------------------------ #
    # Public generation methods                                          #
    # ------------------------------------------------------------------ #
    def generate_tailored_resume(
        self,
        job_description: str,
        company: str,
        role: str,
        job_context: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Produce a tailored resume in plain text format.
        """
        self._ensure_resume_loaded()
        context = dict(self._resume_context)
        job_ctx = job_context or self._build_job_context(job_description, company, role)
        context.update(job_ctx)

        sections: List[str] = []

        # Header (always included)
        header = self.generate_header(context)
        if header:
            sections.append(header)

        # Summary
        summary_section = self.generate_summary_section(context)
        if summary_section:
            sections.append(summary_section)

        # Experience
        if context.get("experience_details"):
            experience_section = self.generate_work_experience_section(context)
            if experience_section:
                sections.append(experience_section)

        # Projects
        if context.get("projects"):
            projects_section = self.generate_projects_section(context)
            if projects_section:
                sections.append(projects_section)

        # Education
        if context.get("education_details"):
            education_section = self.generate_education_section(context)
            if education_section:
                sections.append(education_section)

        # Achievements
        if context.get("achievements"):
            achievements_section = self.generate_achievements_section(context)
            if achievements_section:
                sections.append(achievements_section)

        # Certifications
        if context.get("certifications"):
            certifications_section = self.generate_certifications_section(context)
            if certifications_section:
                sections.append(certifications_section)

        # Additional skills
        if any(
            context.get(field)
            for field in ("skills", "languages", "interests", "additional_notes")
        ):
            additional_skills_section = self.generate_additional_skills_section(context)
            if additional_skills_section:
                sections.append(additional_skills_section)

        resume_output = "\n\n".join(sec.strip() for sec in sections if sec.strip())
        logger.debug("Generated tailored resume with {} sections", len(sections))
        return resume_output.strip()

    def generate_cover_letter(
        self,
        job_description: str,
        company: str,
        role: str,
        job_context: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Generate a tailored cover letter body (no greeting or signature).
        """
        self._ensure_resume_loaded()
        context = dict(self._resume_context)
        job_ctx = job_context or self._build_job_context(job_description, company, role)
        context.update(job_ctx)
        cover_letter = self._invoke_prompt(
            self.strings.cover_letter, context, llm=self.llm_cover
        )
        logger.debug("Generated cover letter ({} chars)", len(cover_letter))
        return cover_letter

    def generate_resume_and_cover_letter(
        self,
        job_description: str,
        company: str,
        role: str,
        parallel: bool = True,
    ) -> Dict[str, str]:
        """
        Convenience helper that returns both resume and cover letter plus the job summary.
        """
        self._ensure_resume_loaded()
        job_ctx = self._build_job_context(job_description, company, role)

        if not parallel:
            resume = self.generate_tailored_resume(
                job_description, company, role, job_context=job_ctx
            )
            cover = self.generate_cover_letter(
                job_description, company, role, job_context=job_ctx
            )
            return {
                "resume": resume,
                "cover_letter": cover,
                "job_summary": job_ctx.get("job_summary", ""),
            }

        with ThreadPoolExecutor(max_workers=2) as executor:
            resume_future = executor.submit(
                self.generate_tailored_resume,
                job_description,
                company,
                role,
                job_ctx,
            )
            cover_future = executor.submit(
                self.generate_cover_letter,
                job_description,
                company,
                role,
                job_ctx,
            )
            resume = resume_future.result()
            cover = cover_future.result()
            return {
                "resume": resume,
                "cover_letter": cover,
                "job_summary": job_ctx.get("job_summary", ""),
            }

    def generate_html_resume(
        self,
        job_description: str = "",
        company: str = "",
        role: str = "",
    ) -> str:
        """
        Generate a simple HTML version of the tailored resume.
        """
        plain_text = self.generate_tailored_resume(job_description, company, role)
        if not plain_text:
            return ""

        sections = plain_text.split("\n\n")
        html_chunks: List[str] = ["<body>"]
        if sections:
            header_lines = sections[0].splitlines()
            html_chunks.append("  <header>")
            for line in header_lines:
                html_chunks.append(f"    <p>{line.strip()}</p>")
            html_chunks.append("  </header>")

        for block in sections[1:]:
            lines = [ln for ln in block.splitlines() if ln.strip()]
            if not lines:
                continue
            heading = lines[0].strip()
            html_chunks.append("  <section>")
            html_chunks.append(f"    <h2>{heading.title()}</h2>")
            paragraphs: List[str] = []
            bullets: List[str] = []
            for line in lines[1:]:
                content = line.strip()
                if content.startswith("•"):
                    bullets.append(content[1:].strip())
                elif content:
                    paragraphs.append(content)
            for paragraph in paragraphs:
                html_chunks.append(f"    <p>{paragraph}</p>")
            if bullets:
                html_chunks.append("    <ul>")
                for bullet in bullets:
                    html_chunks.append(f"      <li>{bullet}</li>")
                html_chunks.append("    </ul>")
            html_chunks.append("  </section>")
        html_chunks.append("</body>")
        html_output = "\n".join(html_chunks)
        logger.debug("Generated HTML resume ({} chars)", len(html_output))
        return html_output


__all__ = ["LLMResumer", "ResumeSections", "ResumePromptLibrary"]
"""
Create a class that generates a resume based on a resume and a resume template.
"""
# app/libs/resume_and_cover_builder/gpt_resume.py
import os
import textwrap
from src.libs.resume_and_cover_builder.utils import LoggerChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Configure log file
log_folder = 'log/resume/gpt_resume'
if not os.path.exists(log_folder):
    os.makedirs(log_folder)
log_path = Path(log_folder).resolve()
logger.add(log_path / "gpt_resume.log", rotation="1 day", compression="zip", retention="7 days", level="DEBUG")

class LLMResumer:
    def __init__(self, openai_api_key, strings):
        self.llm_cheap = LoggerChatModel(
            ChatOpenAI(
                model="gpt-4o-mini", api_key=openai_api_key, temperature=0.4
            )
        )
        self.strings = strings

    @staticmethod
    def _preprocess_template_string(template: str) -> str:
        """
        Preprocess the template string by removing leading whitespace and indentation.
        Args:
            template (str): The template string to preprocess.
        Returns:
            str: The preprocessed template string.
        """
        return textwrap.dedent(template)

    def set_resume(self, resume) -> None:
        """
        Set the resume object to be used for generating the resume.
        Args:
            resume (Resume): The resume object to be used.
        """
        self.resume = resume

    def generate_header(self, data = None) -> str:
        """
        Generate the header section of the resume.
        Args:
            data (dict): The personal information to use for generating the header.
        Returns:
            str: The generated header section.
        """
        header_prompt_template = self._preprocess_template_string(
            self.strings.prompt_header
        )
        prompt = ChatPromptTemplate.from_template(header_prompt_template)
        chain = prompt | self.llm_cheap | StrOutputParser()
        input_data = {
            "personal_information": self.resume.personal_information
        } if data is None else data
        output = chain.invoke(input_data)
        return output
    
    def generate_education_section(self, data = None) -> str:
        """
        Generate the education section of the resume.
        Args:
            data (dict): The education details to use for generating the education section.
        Returns:
            str: The generated education section.
        """
        logger.debug("Starting education section generation")

        education_prompt_template = self._preprocess_template_string(self.strings.prompt_education)
        logger.debug(f"Education template: {education_prompt_template}")

        prompt = ChatPromptTemplate.from_template(education_prompt_template)
        logger.debug(f"Prompt: {prompt}")
        
        chain = prompt | self.llm_cheap | StrOutputParser()
        logger.debug(f"Chain created: {chain}")
        
        input_data = {
            "education_details": self.resume.education_details
        } if data is None else data
        output = chain.invoke(input_data)
        logger.debug(f"Chain invocation result: {output}")

        logger.debug("Education section generation completed")
        return output

    def generate_work_experience_section(self, data = None) -> str:
        """
        Generate the work experience section of the resume.
        Args:
            data (dict): The work experience details to use for generating the work experience section.
        Returns:
            str: The generated work experience section.
        """
        logger.debug("Starting work experience section generation")

        work_experience_prompt_template = self._preprocess_template_string(self.strings.prompt_working_experience)
        logger.debug(f"Work experience template: {work_experience_prompt_template}")

        prompt = ChatPromptTemplate.from_template(work_experience_prompt_template)
        logger.debug(f"Prompt: {prompt}")
        
        chain = prompt | self.llm_cheap | StrOutputParser()
        logger.debug(f"Chain created: {chain}")
        
        input_data = {
            "experience_details": self.resume.experience_details
        } if data is None else data
        output = chain.invoke(input_data)
        logger.debug(f"Chain invocation result: {output}")

        logger.debug("Work experience section generation completed")
        return output

    def generate_projects_section(self, data = None) -> str:
        """
        Generate the side projects section of the resume.
        Args:
            data (dict): The side projects to use for generating the side projects section.
        Returns:
            str: The generated side projects section.
        """
        logger.debug("Starting side projects section generation")

        projects_prompt_template = self._preprocess_template_string(self.strings.prompt_projects)
        logger.debug(f"Side projects template: {projects_prompt_template}")

        prompt = ChatPromptTemplate.from_template(projects_prompt_template)
        logger.debug(f"Prompt: {prompt}")
        
        chain = prompt | self.llm_cheap | StrOutputParser()
        logger.debug(f"Chain created: {chain}")
        
        input_data = {
            "projects": self.resume.projects
        } if data is None else data
        output = chain.invoke(input_data)
        logger.debug(f"Chain invocation result: {output}")

        logger.debug("Side projects section generation completed")
        return output

    def generate_achievements_section(self, data = None) -> str:
        """
        Generate the achievements section of the resume.
        Args:
            data (dict): The achievements to use for generating the achievements section.
        Returns:
            str: The generated achievements section.
        """
        logger.debug("Starting achievements section generation")

        achievements_prompt_template = self._preprocess_template_string(self.strings.prompt_achievements)
        logger.debug(f"Achievements template: {achievements_prompt_template}")

        prompt = ChatPromptTemplate.from_template(achievements_prompt_template)
        logger.debug(f"Prompt: {prompt}")

        chain = prompt | self.llm_cheap | StrOutputParser()
        logger.debug(f"Chain created: {chain}")

        input_data = {
            "achievements": self.resume.achievements,
            "certifications": self.resume.certifications,
        } if data is None else data
        logger.debug(f"Input data for the chain: {input_data}")

        output = chain.invoke(input_data)
        logger.debug(f"Chain invocation result: {output}")

        logger.debug("Achievements section generation completed")
        return output

    def generate_certifications_section(self, data = None) -> str:
        """
        Generate the certifications section of the resume.
        Returns:
            str: The generated certifications section.
        """
        logger.debug("Starting Certifications section generation")

        certifications_prompt_template = self._preprocess_template_string(self.strings.prompt_certifications)
        logger.debug(f"Certifications template: {certifications_prompt_template}")

        prompt = ChatPromptTemplate.from_template(certifications_prompt_template)
        logger.debug(f"Prompt: {prompt}")

        chain = prompt | self.llm_cheap | StrOutputParser()
        logger.debug(f"Chain created: {chain}")

        input_data = {
            "certifications": self.resume.certifications
        } if data is None else data
        logger.debug(f"Input data for the chain: {input_data}")

        output = chain.invoke(input_data)
        logger.debug(f"Chain invocation result: {output}")

        logger.debug("Certifications section generation completed")
        return output
    
    def generate_additional_skills_section(self, data = None) -> str:
        """
        Generate the additional skills section of the resume.
        Returns:
            str: The generated additional skills section.
        """
        additional_skills_prompt_template = self._preprocess_template_string(self.strings.prompt_additional_skills)
        
        skills = set()
        if self.resume.experience_details:
            for exp in self.resume.experience_details:
                if exp.skills_acquired:
                    skills.update(exp.skills_acquired)

        if self.resume.education_details:
            for edu in self.resume.education_details:
                if edu.exam:
                    for exam in edu.exam:
                        skills.update(exam.keys())
        prompt = ChatPromptTemplate.from_template(additional_skills_prompt_template)
        chain = prompt | self.llm_cheap | StrOutputParser()
        input_data = {
            "languages": self.resume.languages,
            "interests": self.resume.interests,
            "skills": skills,
        } if data is None else data
        output = chain.invoke(input_data)
        
        return output

    def generate_html_resume(self) -> str:
        """
        Generate the full HTML resume based on the resume object.
        Returns:
            str: The generated HTML resume.
        """
        def header_fn():
            if self.resume.personal_information:
                return self.generate_header()
            return ""

        def education_fn():
            if self.resume.education_details:
                return self.generate_education_section()
            return ""

        def work_experience_fn():
            if self.resume.experience_details:
                return self.generate_work_experience_section()
            return ""

        def projects_fn():
            if self.resume.projects:
                return self.generate_projects_section()
            return ""

        def achievements_fn():
            if self.resume.achievements:
                return self.generate_achievements_section()
            return ""
        
        def certifications_fn():
            if self.resume.certifications:
                return self.generate_certifications_section()
            return ""

        def additional_skills_fn():
            if (self.resume.experience_details or self.resume.education_details or
                self.resume.languages or self.resume.interests):
                return self.generate_additional_skills_section()
            return ""

        # Create a dictionary to map the function names to their respective callables
        functions = {
            "header": header_fn,
            "education": education_fn,
            "work_experience": work_experience_fn,
            "projects": projects_fn,
            "achievements": achievements_fn,
            "certifications": certifications_fn,
            "additional_skills": additional_skills_fn,
        }

        # Use ThreadPoolExecutor to run the functions in parallel
        with ThreadPoolExecutor() as executor:
            future_to_section = {executor.submit(fn): section for section, fn in functions.items()}
            results = {}
            for future in as_completed(future_to_section):
                section = future_to_section[future]
                try:
                    result = future.result()
                    if result:
                        results[section] = result
                except Exception as exc:
                    logger.error(f'{section} raised an exception: {exc}')
        full_resume = "<body>\n"
        full_resume += f"  {results.get('header', '')}\n"
        full_resume += "  <main>\n"
        full_resume += f"    {results.get('education', '')}\n"
        full_resume += f"    {results.get('work_experience', '')}\n"
        full_resume += f"    {results.get('projects', '')}\n"
        full_resume += f"    {results.get('achievements', '')}\n"
        full_resume += f"    {results.get('certifications', '')}\n"
        full_resume += f"    {results.get('additional_skills', '')}\n"
        full_resume += "  </main>\n"
        full_resume += "</body>"
        return full_resume
