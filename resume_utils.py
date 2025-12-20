from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Tuple

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore


def load_resume_data(path: Path) -> Tuple[str, dict[str, Any] | None]:
    """
    Load resume content. Supports plain text and YAML.

    Returns:
        tuple[str, dict]: (rendered_text, structured_data_or_None)
    """
    suffix = path.suffix.lower()
    raw = path.read_text(encoding="utf-8")
    if suffix in {".yml", ".yaml"}:
        # If PyYAML isn't installed, treat YAML as plain text so matching can still run.
        if yaml is None:
            return raw, None
        data = yaml.safe_load(raw) or {}
        rendered = render_resume_from_yaml(data)
        return rendered, data
    return raw, None


def render_resume_from_yaml(data: dict[str, Any]) -> str:
    """Render a structured resume dictionary into plain text."""
    parts: list[str] = []

    basics = data.get("basics") or {}
    name = basics.get("name")
    if name:
        parts.append(name)
    contact_bits = [
        basics.get("phone"),
        basics.get("email"),
    ]
    for profile in basics.get("profiles") or []:
        network = profile.get("network")
        url = profile.get("url") or profile.get("username")
        if network and url:
            contact_bits.append(f"{network}: {url}")
    contact_line = " | ".join(bit for bit in contact_bits if bit)
    if contact_line:
        parts.append(contact_line)

    summary = basics.get("summary") or basics.get("summary_lines") or []
    if summary:
        parts.append("")
        parts.append("PROFESSIONAL SUMMARY")
        parts.extend(_bullet(summary))

    skills = data.get("skills") or []
    if skills:
        parts.append("")
        parts.append("TECHNICAL SKILLS")
        for skill in skills:
            name = skill.get("name")
            keywords = skill.get("keywords") or []
            if name and keywords:
                parts.append(f"{name}: {', '.join(keywords)}")

    experience = data.get("work") or []
    if experience:
        parts.append("")
        parts.append("PROFESSIONAL EXPERIENCE")
        for job in experience:
            title = job.get("position") or job.get("title") or ""
            company = job.get("company") or ""
            location = job.get("location") or ""
            header = " | ".join(part for part in [title.strip(), company.strip()] if part)
            if header:
                parts.append(header)
            dates = " – ".join(
                part
                for part in [job.get("startDate") or job.get("start_date"), job.get("endDate") or job.get("end_date")]
                if part
            )
            if dates or location:
                loc_dates = " | ".join(part for part in [dates, location] if part)
                parts.append(loc_dates)
            tech = job.get("technologies") or []
            if tech:
                parts.append(f"Technologies: {', '.join(tech)}")
            highlights = job.get("highlights") or job.get("responsibilities") or []
            if highlights:
                parts.extend(_bullet(highlights))
            achievements = job.get("achievements") or []
            if achievements:
                parts.append("Achievements:")
                parts.extend(_bullet(achievements, indent="  "))
            parts.append("")
        if parts and not parts[-1].strip():
            parts.pop()

    education = data.get("education") or []
    if education:
        parts.append("")
        parts.append("EDUCATION")
        for edu in education:
            inst = edu.get("institution") or ""
            degree = edu.get("studyType") or edu.get("degree") or ""
            area = edu.get("area") or ""
            header = " | ".join(part for part in [degree, area, inst] if part)
            if header:
                parts.append(header)
            dates = " – ".join(part for part in [edu.get("startDate"), edu.get("endDate")] if part)
            if dates:
                parts.append(dates)
            gpa = edu.get("gpa")
            if gpa:
                parts.append(f"GPA: {gpa}")
            notes = edu.get("notes")
            if notes:
                if isinstance(notes, str):
                    parts.append(notes)
                else:
                    parts.extend(_bullet(notes))

    projects = data.get("projects") or []
    if projects:
        parts.append("")
        parts.append("PROJECTS")
        for proj in projects:
            line = proj.get("name")
            if line:
                parts.append(line)
            desc = proj.get("description")
            if desc:
                parts.append(desc)
            contribs = proj.get("contributions") or []
            if contribs:
                parts.extend(_bullet(contribs))
            tech = proj.get("technologies") or []
            if tech:
                parts.append(f"Technologies: {', '.join(tech)}")

    publications = data.get("publications") or []
    if publications:
        parts.append("")
        parts.append("PUBLICATIONS")
        for pub in publications:
            title = pub.get("name") or pub.get("title")
            cite_bits = [pub.get("publisher"), pub.get("releaseDate") or pub.get("year"), pub.get("url")]
            citation = " | ".join(bit for bit in cite_bits if bit)
            if title:
                parts.append(f"{title}{' — ' + citation if citation else ''}")
            if pub.get("summary"):
                parts.append(pub["summary"])

    awards = data.get("awards") or []
    if awards:
        parts.append("")
        parts.append("AWARDS")
        for award in awards:
            if isinstance(award, str):
                parts.append(f"• {award}")
            else:
                name = award.get("title") or award.get("name")
                date = award.get("date")
                award_line = " – ".join(bit for bit in [name, date] if bit)
                if award_line:
                    parts.append(f"• {award_line}")

    return "\n".join(parts).strip()


def _bullet(items: Iterable[Any], indent: str = "") -> list[str]:
    result = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, (list, tuple)):
            for sub in item:
                if sub:
                    result.append(f"{indent}• {str(sub).strip()}")
        else:
            text = str(item).strip()
            if text:
                result.append(f"{indent}• {text}")
    return result

