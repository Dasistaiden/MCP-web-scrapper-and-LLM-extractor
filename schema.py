"""
schema.py — School Profile Data Structure
==========================================
Edit this file to add, remove, or rename fields.
Changes here automatically propagate to the LLM prompt and output validation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────────────────────────────────────

class BasicDetails(BaseModel):
    name: str = Field(description="Official full name of the institution")
    address: Optional[str] = Field(None, description="Full street address including city and country")
    phone: Optional[str] = Field(None, description="Main switchboard phone number")
    email: Optional[str] = Field(None, description="Main contact or admissions email")
    institution_type: Optional[str] = Field(None, description="'public' or 'private'")
    year_founded: Optional[int] = Field(None, description="Year the institution was established")
    website: Optional[str] = Field(None, description="Official website URL")


class KeyContact(BaseModel):
    name: Optional[str] = Field(None, description="Full name of the person")
    title: str = Field(description="Job title, e.g. President, Rector, Dean, Head of International Office")
    department_or_office: Optional[str] = Field(None, description="Office or department they belong to")
    email: Optional[str] = Field(None, description="Direct email address")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL (to be verified later)")
    facebook_url: Optional[str] = Field(None, description="Facebook profile URL (to be verified later)")
    verification_status: str = Field(
        default="unverified",
        description="Employment verification status: 'unverified' | 'verified' | 'inactive'"
    )


class Department(BaseModel):
    name: str = Field(description="Department name, e.g. Engineering, Business, Science, Arts")
    description: Optional[str] = Field(None, description="Short description of the department")
    subjects: List[str] = Field(
        default_factory=list,
        description="List of subjects or courses taught in this department"
    )


class DegreeProgram(BaseModel):
    name: str = Field(description="Full program name")
    level: str = Field(description="Degree level: 'Bachelor' | 'Master' | 'Doctorate' | 'Certificate' | 'Diploma'")
    department: Optional[str] = Field(None, description="Which department offers this program")
    duration: Optional[str] = Field(None, description="Program length, e.g. '3 years', '4 semesters'")
    language_of_instruction: Optional[str] = Field(None, description="Language courses are taught in")
    tuition_fee: Optional[str] = Field(None, description="Tuition fee info, e.g. '€5,000/year', 'Fee-HELP available'")
    entry_requirements: Optional[str] = Field(None, description="Admission requirements summary")
    subjects: List[str] = Field(
        default_factory=list,
        description="Key subjects or specialisations within this program"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Root model — one object per school
# ─────────────────────────────────────────────────────────────────────────────

class SchoolProfile(BaseModel):
    # Metadata (filled automatically by extractor, not by LLM)
    domain: str
    source_url: str
    extracted_at: str
    extraction_model: str

    # LLM-extracted fields
    basic_details: BasicDetails
    key_contacts: List[KeyContact] = Field(default_factory=list)
    departments: List[Department] = Field(default_factory=list)
    degree_programs: List[DegreeProgram] = Field(default_factory=list)
    extraction_notes: Optional[str] = Field(
        None,
        description="Any caveats: missing data, ambiguous content, low confidence fields"
    )


# ─────────────────────────────────────────────────────────────────────────────
# JSON template shown to Claude in the prompt
# (auto-generated from the models above — do not edit manually)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Schema-driven crawl hints
# Maps each schema field to URL keywords that suggest a page contains that data.
# Used by run_scraper.py to skip irrelevant pages during crawling.
# Add keywords here whenever your schema gains new fields.
# ─────────────────────────────────────────────────────────────────────────────

FIELD_URL_HINTS: dict[str, list[str]] = {
    "basic_details": [
        "about", "introduction", "overview", "mission", "vision",
        "history", "profile", "institution", "who-we-are",
        # PDFs with fee / cost info
        "fee", "fees", "tuition", "cost", "price", "tariff",
        "domestic", "international",
    ],
    "key_contacts": [
        "people", "staff", "team", "faculty", "board", "governance",
        "contact", "leadership", "management", "directory",
        "president", "rector", "dean", "principal", "international",
    ],
    "departments": [
        "department", "faculty", "school", "college", "division",
        "institute", "centre", "center", "unit",
    ],
    "degree_programs": [
        "course", "program", "programme", "degree", "qualification",
        "bachelor", "master", "doctorate", "phd", "diploma", "certificate",
        "postgrad", "postgraduate", "undergrad", "undergraduate",
        "study", "studies", "curriculum", "offering",
        # PDF filenames commonly used by universities
        "handbook", "prospectus", "catalog", "catalogue", "brochure",
        "syllabus", "guide", "schedule",
        # domain-specific (music/arts example — safe to keep, unused on other sites)
        "contemporary", "classical", "jazz", "dance", "composition",
        "music-theatre", "performance",
    ],
}

# Flat set of all keywords for fast O(1) membership check
_ALL_URL_HINTS: frozenset[str] = frozenset(
    kw for hints in FIELD_URL_HINTS.values() for kw in hints
)


def url_matches_schema(url: str) -> bool:
    """
    Return True if the URL contains at least one keyword from FIELD_URL_HINTS.
    Used by run_scraper.py to skip pages that are unlikely to hold schema data.
    The homepage (very short path) is always considered relevant.
    """
    from urllib.parse import urlparse
    path = urlparse(url).path.lower().rstrip("/")
    # Homepage or first-level path: always include
    if path.count("/") <= 1:
        return True
    return any(kw in path for kw in _ALL_URL_HINTS)


EXTRACTION_TEMPLATE = {
    "basic_details": {
        "name": "string — official institution name",
        "address": "string or null",
        "phone": "string or null",
        "email": "string or null",
        "institution_type": "'public' or 'private' or null",
        "year_founded": "integer or null",
        "website": "string or null"
    },
    "key_contacts": [
        {
            "name": "string or null",
            "title": "string — job title",
            "department_or_office": "string or null",
            "email": "string or null",
            "linkedin_url": "string or null",
            "facebook_url": "string or null",
            "verification_status": "'unverified'"
        }
    ],
    "departments": [
        {
            "name": "string — department name",
            "description": "string or null",
            "subjects": ["subject1", "subject2"]
        }
    ],
    "degree_programs": [
        {
            "name": "string — program name",
            "level": "Bachelor | Master | Doctorate | Certificate | Diploma",
            "department": "string or null",
            "duration": "string or null",
            "language_of_instruction": "string or null",
            "tuition_fee": "string or null",
            "entry_requirements": "string or null",
            "subjects": ["subject1", "subject2"]
        }
    ],
    "extraction_notes": "string or null — note any missing/uncertain data"
}
