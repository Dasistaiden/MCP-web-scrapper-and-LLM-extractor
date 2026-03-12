"""
schema.py — School Profile Data Structure (IAU WHED field specifications)
==========================================================================
Priority levels (IAU-Categorisation):
  Required      : Must extract; LLM actively seeks these fields
  Important     : Extract when clearly stated on the page
  Nice-to-have  : Extract only if directly visible
  Supplemental  : Skip if not immediately obvious
  Not Collected : Excluded from schema entirely

Edit this file to add, remove, or rename fields.
Changes here automatically propagate to the LLM prompt, output validation,
and schema-driven crawl hints.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────────────────────────────────────

class OrgBasics(BaseModel):
    # ── Required ──────────────────────────────────────────────────────────────
    name_native: str = Field(
        description="REQUIRED: Official institution name in native language or transliteration"
    )
    name_english: str = Field(
        description="REQUIRED: Official institution name in English"
    )
    is_branch: Optional[bool] = Field(
        None,
        description="REQUIRED: True if this is a branch campus of another institution"
    )
    year_founded: Optional[int] = Field(
        None,
        description="REQUIRED: Year the institution was established (use 0 if unknown)"
    )
    institution_type_international: Optional[str] = Field(
        None,
        description=(
            "REQUIRED: IAU international classification. One of: "
            "UV (University), OI (Other Institution), NA, NC, MR, PB, DU, UD, ME, SN"
        )
    )
    institution_type_national: Optional[str] = Field(
        None,
        description="REQUIRED: National institution type as classified in the country"
    )
    funding_type: Optional[str] = Field(
        None,
        description=(
            "REQUIRED: Funding type. One of: "
            "Pu (Public), Pr (Private), Pp (Public-Private), Mi (Mixed), Un (Unknown)"
        )
    )
    # ── Nice-to-have ──────────────────────────────────────────────────────────
    year_acquired_status: Optional[int] = Field(
        None,
        description="NICE-TO-HAVE: Year the institution acquired its current status (e.g. became a university)"
    )
    other_campuses: Optional[str] = Field(
        None,
        description="NICE-TO-HAVE: Other campus locations (city or address)"
    )
    # ── Supplemental ──────────────────────────────────────────────────────────
    acronym: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Official acronym or abbreviation of the institution name"
    )


class ContactInfo(BaseModel):
    # ── Required ──────────────────────────────────────────────────────────────
    city: Optional[str] = Field(
        None,
        description="REQUIRED: City where the institution is located"
    )
    # ── Important ─────────────────────────────────────────────────────────────
    street: Optional[str] = Field(
        None,
        description="IMPORTANT: Street address of the institution"
    )
    province: Optional[str] = Field(
        None,
        description="IMPORTANT: Province, state, or region"
    )
    post_code: Optional[str] = Field(
        None,
        description="IMPORTANT: Postal or ZIP code"
    )
    website: Optional[str] = Field(
        None,
        description="IMPORTANT: Official website URL"
    )
    # ── Nice-to-have ──────────────────────────────────────────────────────────
    email: Optional[str] = Field(
        None,
        description="NICE-TO-HAVE: Main contact or admissions email address"
    )
    # ── Supplemental ──────────────────────────────────────────────────────────
    phone: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Main switchboard phone number"
    )


class AcademicInfo(BaseModel):
    # ── Important ─────────────────────────────────────────────────────────────
    languages_of_instruction: List[str] = Field(
        default_factory=list,
        description="IMPORTANT: Languages in which courses are taught (e.g. ['English', 'French'])"
    )
    accrediting_body: Optional[str] = Field(
        None,
        description="IMPORTANT: Name of the accrediting agency or body"
    )
    history: Optional[str] = Field(
        None,
        description="IMPORTANT: Brief summary of the institution's history"
    )
    # ── Supplemental ──────────────────────────────────────────────────────────
    academic_year: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Academic year structure (e.g. 'September to June, two semesters')"
    )
    admission_requirements: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: General admission requirements summary"
    )
    student_body: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Student body composition. One of: Co-ed, Female-only, Male-only"
    )
    learning_modalities: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Teaching modalities. One of: Traditional, Online, Both"
    )


class TuitionInfo(BaseModel):
    # ── Nice-to-have ──────────────────────────────────────────────────────────
    national_students: Optional[str] = Field(
        None,
        description="NICE-TO-HAVE: Average tuition fees for domestic/national students (include currency)"
    )
    international_students: Optional[str] = Field(
        None,
        description="NICE-TO-HAVE: Average tuition fees for international students (include currency)"
    )


class KeyContact(BaseModel):
    # ── Required ──────────────────────────────────────────────────────────────
    first_name: Optional[str] = Field(
        None,
        description="REQUIRED: First name of the contact person"
    )
    surname: Optional[str] = Field(
        None,
        description="REQUIRED: Surname / family name of the contact person"
    )
    job_title: Optional[str] = Field(
        None,
        description="REQUIRED: Formal job title (e.g. President, Rector, Dean)"
    )
    job_function: Optional[str] = Field(
        None,
        description=(
            "REQUIRED: Job function category. One of: "
            "Head of Institution, Senior Admin Officer, International Relations Officer"
        )
    )
    # ── Important ─────────────────────────────────────────────────────────────
    email: Optional[str] = Field(
        None,
        description="IMPORTANT: Direct email address of the contact"
    )
    gender: Optional[str] = Field(
        None,
        description="IMPORTANT: Gender of the contact person"
    )
    # ── Nice-to-have ──────────────────────────────────────────────────────────
    years_of_office: Optional[str] = Field(
        None,
        description=(
            "NICE-TO-HAVE: Period in office, e.g. 'January 2020 -' or '2018 - 2023'. "
            "Use 'YYYY -' if still in office."
        )
    )
    # ── Supplemental ──────────────────────────────────────────────────────────
    phone: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Direct phone number of the contact"
    )
    # ── Metadata ──────────────────────────────────────────────────────────────
    verification_status: str = Field(
        default="unverified",
        description="Employment verification status: 'unverified' | 'verified' | 'inactive'"
    )


class Division(BaseModel):
    # ── Required ──────────────────────────────────────────────────────────────
    name: str = Field(
        description="REQUIRED: Division name (e.g. Faculty of Engineering, School of Business)"
    )
    division_type: Optional[str] = Field(
        None,
        description=(
            "REQUIRED: Type of division. One of: "
            "Faculty, School, Department, Institute, Centre, College, Other"
        )
    )
    fields_of_study: List[str] = Field(
        default_factory=list,
        description="REQUIRED: Fields of study or disciplines taught in this division"
    )
    # ── Supplemental ──────────────────────────────────────────────────────────
    details: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Additional details, e.g. campus location or short description"
    )


class DegreeProgram(BaseModel):
    # ── Required ──────────────────────────────────────────────────────────────
    name: str = Field(
        description="REQUIRED: Full credential name (e.g. Bachelor of Business Administration)"
    )
    level: str = Field(
        description="REQUIRED: Degree level: 'Bachelor' | 'Master' | 'Doctorate' | 'Certificate' | 'Diploma'"
    )
    # ── Enrichment (extract when available) ───────────────────────────────────
    department: Optional[str] = Field(
        None,
        description="Division or faculty offering this program"
    )
    duration: Optional[str] = Field(
        None,
        description="Program length, e.g. '3 years', '4 semesters'"
    )
    language_of_instruction: Optional[str] = Field(
        None,
        description="Language courses are taught in for this program"
    )
    tuition_fee: Optional[str] = Field(
        None,
        description="Tuition fee for this specific program (include currency)"
    )
    entry_requirements: Optional[str] = Field(
        None,
        description="Admission requirements summary for this program"
    )


class OtherInfo(BaseModel):
    # ── Supplemental ──────────────────────────────────────────────────────────
    student_numbers: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Enrollment numbers (male, female, students with disabilities)"
    )
    institutional_publications: Optional[str] = Field(
        None,
        description="SUPPLEMENTAL: Notable institutional publications or research outputs"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Root model — one object per institution
# ─────────────────────────────────────────────────────────────────────────────

class SchoolProfile(BaseModel):
    # Metadata (filled automatically by extractor, not by LLM)
    domain: str
    source_url: str
    extracted_at: str
    extraction_model: str

    # LLM-extracted fields
    org_basics: OrgBasics
    contact: ContactInfo
    academic: AcademicInfo
    tuition: TuitionInfo
    key_contacts: List[KeyContact] = Field(default_factory=list)
    divisions: List[Division] = Field(default_factory=list)
    degree_programs: List[DegreeProgram] = Field(default_factory=list)
    other: Optional[OtherInfo] = None
    extraction_notes: Optional[str] = Field(
        None,
        description="Any caveats: missing data, ambiguous content, low-confidence fields"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Schema-driven crawl hints
# Maps each schema section to URL keywords suggesting a page contains that data.
# Used by run_scraper.py to skip irrelevant pages during crawling.
# ─────────────────────────────────────────────────────────────────────────────

FIELD_URL_HINTS: dict[str, list[str]] = {
    "org_basics": [
        "about", "introduction", "overview", "mission", "vision",
        "history", "profile", "institution", "who-we-are", "background",
        "governance", "charter", "foundation", "founding",
    ],
    "contact": [
        "contact", "address", "location", "find-us", "directions", "map",
        "reach-us", "get-in-touch",
    ],
    "academic": [
        "academic", "accreditation", "accredited", "recognition",
        "admission", "admissions", "requirements", "entry",
        "language", "languages", "instruction",
        "academic-year", "calendar", "semester",
    ],
    "tuition": [
        "fee", "fees", "tuition", "cost", "costs", "price", "pricing",
        "tariff", "domestic", "international", "scholarship", "financial",
    ],
    "key_contacts": [
        "people", "staff", "team", "faculty", "board", "governance",
        "contact", "leadership", "management", "directory",
        "president", "rector", "dean", "principal", "international",
        "administration", "executive", "officer",
    ],
    "divisions": [
        "department", "faculty", "school", "college", "division",
        "institute", "centre", "center", "unit", "academy",
    ],
    "degree_programs": [
        "course", "courses", "program", "programme", "programs", "programmes",
        "degree", "qualification", "offering", "offerings",
        "bachelor", "master", "doctorate", "phd", "diploma", "certificate",
        "postgrad", "postgraduate", "undergrad", "undergraduate",
        "study", "studies", "curriculum",
        "handbook", "prospectus", "catalog", "catalogue", "brochure",
        "syllabus", "guide", "schedule",
    ],
}

# Flat set of all keywords for fast O(1) membership check
_ALL_URL_HINTS: frozenset[str] = frozenset(
    kw for hints in FIELD_URL_HINTS.values() for kw in hints
)


def url_matches_schema(url: str) -> bool:
    """
    Return True if the URL contains at least one keyword from FIELD_URL_HINTS.
    Used by run_scraper.py to skip pages unlikely to hold schema data.
    The homepage and first-level paths are always considered relevant.
    """
    from urllib.parse import urlparse
    path = urlparse(url).path.lower().rstrip("/")
    if path.count("/") <= 1:
        return True
    return any(kw in path for kw in _ALL_URL_HINTS)


# ─────────────────────────────────────────────────────────────────────────────
# JSON template shown to the LLM in the extraction prompt
# (auto-generated from the models above — do not edit manually)
# ─────────────────────────────────────────────────────────────────────────────

EXTRACTION_TEMPLATE = {
    "org_basics": {
        "name_native": "string — REQUIRED: official name in native language",
        "name_english": "string — REQUIRED: official name in English",
        "is_branch": "boolean or null — REQUIRED: true if branch campus",
        "year_founded": "integer or null — REQUIRED: e.g. 1905 (use 0 if unknown)",
        "institution_type_international": "string or null — REQUIRED: UV / OI / NA / NC / MR / PB / DU / UD / ME / SN",
        "institution_type_national": "string or null — REQUIRED: national classification",
        "funding_type": "string or null — REQUIRED: Pu / Pr / Pp / Mi / Un",
        "year_acquired_status": "integer or null — NICE-TO-HAVE",
        "other_campuses": "string or null — NICE-TO-HAVE",
        "acronym": "string or null — SUPPLEMENTAL"
    },
    "contact": {
        "city": "string or null — REQUIRED",
        "street": "string or null — IMPORTANT",
        "province": "string or null — IMPORTANT",
        "post_code": "string or null — IMPORTANT",
        "website": "string or null — IMPORTANT",
        "email": "string or null — NICE-TO-HAVE",
        "phone": "string or null — SUPPLEMENTAL"
    },
    "academic": {
        "languages_of_instruction": ["language1", "language2"],
        "accrediting_body": "string or null — IMPORTANT",
        "history": "string or null — IMPORTANT: brief summary",
        "academic_year": "string or null — SUPPLEMENTAL",
        "admission_requirements": "string or null — SUPPLEMENTAL",
        "student_body": "Co-ed | Female-only | Male-only | null — SUPPLEMENTAL",
        "learning_modalities": "Traditional | Online | Both | null — SUPPLEMENTAL"
    },
    "tuition": {
        "national_students": "string or null — NICE-TO-HAVE: e.g. '€5,000/year'",
        "international_students": "string or null — NICE-TO-HAVE: e.g. '€8,000/year'"
    },
    "key_contacts": [
        {
            "first_name": "string or null — REQUIRED",
            "surname": "string or null — REQUIRED",
            "job_title": "string or null — REQUIRED: e.g. President, Rector, Dean",
            "job_function": "Head of Institution | Senior Admin Officer | International Relations Officer | null — REQUIRED",
            "email": "string or null — IMPORTANT",
            "gender": "string or null — IMPORTANT",
            "years_of_office": "string or null — NICE-TO-HAVE: e.g. 'January 2020 -'",
            "phone": "string or null — SUPPLEMENTAL",
            "verification_status": "'unverified'"
        }
    ],
    "divisions": [
        {
            "name": "string — REQUIRED: division name",
            "division_type": "Faculty | School | Department | Institute | Centre | College | Other | null — REQUIRED",
            "fields_of_study": ["field1", "field2"],
            "details": "string or null — SUPPLEMENTAL"
        }
    ],
    "degree_programs": [
        {
            "name": "string — REQUIRED: full credential name",
            "level": "Bachelor | Master | Doctorate | Certificate | Diploma — REQUIRED",
            "department": "string or null",
            "duration": "string or null",
            "language_of_instruction": "string or null",
            "tuition_fee": "string or null",
            "entry_requirements": "string or null"
        }
    ],
    "other": {
        "student_numbers": "string or null — SUPPLEMENTAL",
        "institutional_publications": "string or null — SUPPLEMENTAL"
    },
    "extraction_notes": "string or null — note any missing or uncertain data"
}
