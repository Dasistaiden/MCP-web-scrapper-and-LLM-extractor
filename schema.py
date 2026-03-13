"""
schema.py — School Profile Data Structure (IAU WHED field specifications)
==========================================================================
Priority levels (IAU-Categorisation):
  Required      : Must extract; LLM actively seeks these fields
  ── Below are DEFERRED (kept for future use, not sent to LLM) ──
  Important     : Extract when clearly stated on the page
  Nice-to-have  : Extract only if directly visible
  Supplemental  : Skip if not immediately obvious
  Not Collected : Excluded from schema entirely

Current scope: REQUIRED fields only.
Non-required fields are preserved in the Pydantic models (marked DEFERRED)
but excluded from EXTRACTION_TEMPLATE so the LLM focuses on high-priority data.

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
            "Pu (Public), Pr (Private), Pp (Private-for-profit), Mi (Mixed), Un (Unknown)"
        )
    )
    # ── DEFERRED — Nice-to-have ───────────────────────────────────────────────
    year_acquired_status: Optional[int] = Field(
        None,
        description="DEFERRED (Nice-to-have): Year the institution acquired its current status"
    )
    other_campuses: Optional[str] = Field(
        None,
        description="DEFERRED (Nice-to-have): Other campus locations (city or address)"
    )
    # ── DEFERRED — Supplemental ───────────────────────────────────────────────
    acronym: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Official acronym or abbreviation"
    )


class ContactInfo(BaseModel):
    # ── Required ──────────────────────────────────────────────────────────────
    city: Optional[str] = Field(
        None,
        description="REQUIRED: City or suburb/locality where the institution is located (use the most specific locality, e.g. 'Surry Hills' not 'Sydney')"
    )
    # ── DEFERRED — Important ──────────────────────────────────────────────────
    street: Optional[str] = Field(
        None,
        description="DEFERRED (Important): Street address of the institution"
    )
    province: Optional[str] = Field(
        None,
        description="DEFERRED (Important): Province, state, or region"
    )
    post_code: Optional[str] = Field(
        None,
        description="DEFERRED (Important): Postal or ZIP code"
    )
    website: Optional[str] = Field(
        None,
        description="DEFERRED (Important): Official website URL"
    )
    # ── DEFERRED — Nice-to-have ───────────────────────────────────────────────
    email: Optional[str] = Field(
        None,
        description="DEFERRED (Nice-to-have): Main contact or admissions email address"
    )
    # ── DEFERRED — Supplemental ───────────────────────────────────────────────
    phone: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Main switchboard phone number"
    )


class AcademicInfo(BaseModel):
    """All fields in this section are DEFERRED (Important / Supplemental)."""
    # ── DEFERRED — Important ──────────────────────────────────────────────────
    languages_of_instruction: List[str] = Field(
        default_factory=list,
        description="DEFERRED (Important): Languages in which courses are taught"
    )
    accrediting_body: Optional[str] = Field(
        None,
        description="DEFERRED (Important): Name of the accrediting agency or body"
    )
    history: Optional[str] = Field(
        None,
        description="DEFERRED (Important): Brief summary of the institution's history"
    )
    # ── DEFERRED — Supplemental ───────────────────────────────────────────────
    academic_year: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Academic year structure"
    )
    admission_requirements: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): General admission requirements summary"
    )
    student_body: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Co-ed, Female-only, Male-only"
    )
    learning_modalities: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Traditional, Online, Both"
    )


class TuitionInfo(BaseModel):
    """All fields in this section are DEFERRED (Nice-to-have)."""
    # ── DEFERRED — Nice-to-have ───────────────────────────────────────────────
    national_students: Optional[str] = Field(
        None,
        description="DEFERRED (Nice-to-have): Average tuition fees for domestic students"
    )
    international_students: Optional[str] = Field(
        None,
        description="DEFERRED (Nice-to-have): Average tuition fees for international students"
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
            "Head of Institution (code: 1H), "
            "Senior Administrative Officer (code: 2A), "
            "International Relations Officer (code: 3R)"
        )
    )
    # ── DEFERRED — Important ──────────────────────────────────────────────────
    email: Optional[str] = Field(
        None,
        description="DEFERRED (Important): Direct email address of the contact"
    )
    gender: Optional[str] = Field(
        None,
        description="DEFERRED (Important): M (Male), F (Female), X (Other)"
    )
    # ── DEFERRED — Nice-to-have ───────────────────────────────────────────────
    years_of_office: Optional[str] = Field(
        None,
        description="DEFERRED (Nice-to-have): Period in office, e.g. 'January 2020 -'"
    )
    # ── DEFERRED — Supplemental ───────────────────────────────────────────────
    phone: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Direct phone number of the contact"
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
            "Faculty, School, Department/Division, Institute, Centre, College, "
            "Academy, Campus, Campus Abroad, Conservatory, Course/Programme, "
            "Foundation, Graduate School, Group, Laboratory, Research Division, Unit, Chair"
        )
    )
    fields_of_study: List[str] = Field(
        default_factory=list,
        description="REQUIRED: Fields of study or disciplines taught in this division"
    )
    # ── DEFERRED — Supplemental ───────────────────────────────────────────────
    details: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Additional details, e.g. campus location"
    )


class DegreeProgram(BaseModel):
    # ── Required ──────────────────────────────────────────────────────────────
    name: str = Field(
        description="REQUIRED: Full credential name (e.g. Bachelor of Business Administration)"
    )
    level: str = Field(
        description=(
            "REQUIRED: Degree level — use the country-specific credential name from WHED "
            "(e.g. 'Bachelor Degree', 'Master Degree', 'Doctoral Degree', 'Associate Degree', "
            "'Graduate Certificate/Diploma', 'Diploma'). "
            "If unsure, use one of: Bachelor, Master, Doctorate, Certificate, Diploma"
        )
    )
    # ── DEFERRED — Enrichment ─────────────────────────────────────────────────
    department: Optional[str] = Field(
        None,
        description="DEFERRED: Division or faculty offering this program"
    )
    duration: Optional[str] = Field(
        None,
        description="DEFERRED: Program length, e.g. '3 years', '4 semesters'"
    )
    language_of_instruction: Optional[str] = Field(
        None,
        description="DEFERRED: Language courses are taught in for this program"
    )
    tuition_fee: Optional[str] = Field(
        None,
        description="DEFERRED: Tuition fee for this specific program (include currency)"
    )
    entry_requirements: Optional[str] = Field(
        None,
        description="DEFERRED: Admission requirements summary for this program"
    )


class OtherInfo(BaseModel):
    """All fields in this section are DEFERRED (Supplemental)."""
    # ── DEFERRED — Supplemental ───────────────────────────────────────────────
    student_numbers: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Enrollment numbers"
    )
    institutional_publications: Optional[str] = Field(
        None,
        description="DEFERRED (Supplemental): Notable institutional publications"
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
    academic: Optional[AcademicInfo] = None
    tuition: Optional[TuitionInfo] = None
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
    # DEFERRED sections — crawl hints kept for future reactivation
    # "academic": [
    #     "academic", "accreditation", "accredited", "recognition",
    #     "admission", "admissions", "requirements", "entry",
    #     "language", "languages", "instruction",
    #     "academic-year", "calendar", "semester",
    # ],
    # "tuition": [
    #     "fee", "fees", "tuition", "cost", "costs", "price", "pricing",
    #     "tariff", "domestic", "international", "scholarship", "financial",
    # ],
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
# ─────────────────────────────────────────────────────────────────────────────
# REQUIRED fields only — non-required fields are accepted by the Pydantic
# models if the LLM returns them, but are NOT requested in the prompt.
# To reactivate a section, move its fields back from the DEFERRED comments.

EXTRACTION_TEMPLATE = {
    "org_basics": {
        "name_native": "string — REQUIRED: official name in native language",
        "name_english": "string — REQUIRED: official name in English",
        "is_branch": "boolean or null — REQUIRED: true if branch campus",
        "year_founded": "integer or null — REQUIRED: e.g. 1905 (use 0 if unknown)",
        "institution_type_international": "string or null — REQUIRED: UV / OI / NA / NC / MR / PB / DU / UD / ME / SN",
        "institution_type_national": "string or null — REQUIRED: national classification",
        "funding_type": "string or null — REQUIRED: Pu (Public) / Pr (Private) / Pp (Private-for-profit) / Mi (Mixed) / Un (Unknown)",
        # DEFERRED:
        # "year_acquired_status": "integer or null — NICE-TO-HAVE",
        # "other_campuses": "string or null — NICE-TO-HAVE",
        # "acronym": "string or null — SUPPLEMENTAL",
    },
    "contact": {
        "city": "string or null — REQUIRED: use most specific locality (suburb, not metro area)",
        # DEFERRED:
        # "street": "string or null — IMPORTANT",
        # "province": "string or null — IMPORTANT",
        # "post_code": "string or null — IMPORTANT",
        # "website": "string or null — IMPORTANT",
        # "email": "string or null — NICE-TO-HAVE",
        # "phone": "string or null — SUPPLEMENTAL",
    },
    # DEFERRED — entire section (no required fields):
    # "academic": {
    #     "languages_of_instruction": ["language1", "language2"],
    #     "accrediting_body": "string or null — IMPORTANT",
    #     "history": "string or null — IMPORTANT",
    #     "academic_year": "string or null — SUPPLEMENTAL",
    #     "admission_requirements": "string or null — SUPPLEMENTAL",
    #     "student_body": "Co-ed | Female-only | Male-only | null — SUPPLEMENTAL",
    #     "learning_modalities": "Traditional | Online | Both | null — SUPPLEMENTAL",
    # },
    # DEFERRED — entire section (no required fields):
    # "tuition": {
    #     "national_students": "string or null — NICE-TO-HAVE",
    #     "international_students": "string or null — NICE-TO-HAVE",
    # },
    "key_contacts": [
        {
            "first_name": "string or null — REQUIRED",
            "surname": "string or null — REQUIRED",
            "job_title": "string or null — REQUIRED: e.g. President, Rector, Dean",
            "job_function": "Head of Institution | Senior Administrative Officer | International Relations Officer | null — REQUIRED",
            # DEFERRED:
            # "email": "string or null — IMPORTANT",
            # "gender": "M | F | X | null — IMPORTANT",
            # "years_of_office": "string or null — NICE-TO-HAVE",
            # "phone": "string or null — SUPPLEMENTAL",
            "verification_status": "'unverified'",
        }
    ],
    "divisions": [
        {
            "name": "string — REQUIRED: division name",
            "division_type": "Faculty | School | Department/Division | Institute | Centre | College | Academy | Campus | Conservatory | Course/Programme | Graduate School | Research Division | Unit | null — REQUIRED",
            "fields_of_study": ["field1", "field2"],
            # DEFERRED:
            # "details": "string or null — SUPPLEMENTAL",
        }
    ],
    "degree_programs": [
        {
            "name": "string — REQUIRED: full credential name",
            "level": "string — REQUIRED: use country-specific credential name (e.g. 'Bachelor Degree', 'Master Degree', 'Doctoral Degree', 'Associate Degree', 'Graduate Certificate/Diploma', 'Diploma')",
            # DEFERRED:
            # "department": "string or null",
            # "duration": "string or null",
            # "language_of_instruction": "string or null",
            # "tuition_fee": "string or null",
            # "entry_requirements": "string or null",
        }
    ],
    # DEFERRED — entire section (no required fields):
    # "other": {
    #     "student_numbers": "string or null — SUPPLEMENTAL",
    #     "institutional_publications": "string or null — SUPPLEMENTAL",
    # },
    "extraction_notes": "string or null — note any missing or uncertain data",
}
