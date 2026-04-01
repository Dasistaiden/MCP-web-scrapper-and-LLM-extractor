"""
db_reference.py — Query WHED MySQL database for reference data
================================================================
Provides two types of grounding for the LLM extraction prompt:

1. **Picklists**: Valid enum values from lookup tables (InstClassCode,
   FundingType, DivisionType, JobFunction, FOS, Languages, etc.)
2. **Few-shot examples**: Complete institution records from the same
   country, formatted as SchoolProfile JSON.

Both reduce hallucination by showing the LLM what correct output looks like.

Connection details are read from .env:
    WHED_DB_HOST, WHED_DB_PORT, WHED_DB_NAME, WHED_DB_USER, WHED_DB_PASSWORD
"""

import json
import logging
import os
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

import pymysql
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# TLD → WHED CountryCode mapping (common cases; extend as needed)
_TLD_TO_COUNTRY: dict[str, str] = {
    "au": "AU", "at": "AT", "be": "BE", "br": "BR", "ca": "CA",
    "ch": "CH", "cn": "CN", "co": "CO", "cz": "CZ", "de": "DE",
    "dk": "DK", "es": "ES", "fi": "FI", "fr": "FR", "gb": "GB",
    "gr": "GR", "hk": "HK", "hu": "HU", "id": "ID", "ie": "IE",
    "il": "IL", "in": "IN", "it": "IT", "jp": "JP", "ke": "KE",
    "kr": "KR", "mx": "MX", "my": "MY", "ng": "NG", "nl": "NL",
    "no": "NO", "nz": "NZ", "ph": "PH", "pk": "PK", "pl": "PL",
    "pt": "PT", "ro": "RO", "ru": "RU", "sa": "SA", "se": "SE",
    "sg": "SG", "th": "TH", "tr": "TR", "tw": "TW", "uk": "GB",
    "us": "US", "za": "ZA", "edu": "US", "ac": None,
}


# ─────────────────────────────────────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────────────────────────────────────

def _get_connection() -> pymysql.Connection:
    return pymysql.connect(
        host=os.getenv("WHED_DB_HOST", "localhost"),
        port=int(os.getenv("WHED_DB_PORT", "3306")),
        database=os.getenv("WHED_DB_NAME", "whed"),
        user=os.getenv("WHED_DB_USER", "root"),
        password=os.getenv("WHED_DB_PASSWORD", ""),
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )


def is_db_available() -> bool:
    """Quick check whether the WHED database is reachable."""
    try:
        conn = _get_connection()
        conn.close()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Country detection from domain
# ─────────────────────────────────────────────────────────────────────────────

def detect_country_code(domain: str) -> Optional[str]:
    """Guess WHED CountryCode from a website domain's TLD."""
    parts = domain.lower().rstrip(".").split(".")
    if len(parts) < 2:
        return None
    tld = parts[-1]
    if tld in ("edu", "org", "com", "net"):
        second = parts[-2] if len(parts) >= 3 else None
        if second and second in _TLD_TO_COUNTRY:
            return _TLD_TO_COUNTRY[second]
        if tld == "edu":
            return "US"
        return None
    return _TLD_TO_COUNTRY.get(tld)


# ─────────────────────────────────────────────────────────────────────────────
# Picklists — cached for the lifetime of the process
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_picklists() -> dict:
    """Return all lookup-table values as a dict of lists."""
    conn = _get_connection()
    c = conn.cursor()

    def _col(sql: str, col: str) -> list[str]:
        c.execute(sql)
        return [row[col] for row in c.fetchall() if row[col]]

    def _pairs(sql: str, code_col: str, label_col: str) -> list[dict]:
        c.execute(sql)
        return [
            {"code": row[code_col], "label": row[label_col]}
            for row in c.fetchall() if row[code_col]
        ]

    data = {
        "inst_class": _pairs(
            "SELECT InstClassCode, InstClass FROM whed_lex_instclass ORDER BY InstClassSortOrder",
            "InstClassCode", "InstClass",
        ),
        "funding_type": _pairs(
            "SELECT InstFundingTypeCode, InstFundingType FROM whed_lex_instfundingtype ORDER BY InstFundingTypeSortOrder",
            "InstFundingTypeCode", "InstFundingType",
        ),
        "division_type": _pairs(
            "SELECT DivisionTypeCode, DivisionType FROM whed_lex_divisiontype WHERE Niveau=1 ORDER BY OutputSortOrder",
            "DivisionTypeCode", "DivisionType",
        ),
        "job_function": _pairs(
            "SELECT JobFunctionCode, JobFunction FROM whed_lex_jobfunction ORDER BY JobFunctionID",
            "JobFunctionCode", "JobFunction",
        ),
        "fos": _col(
            "SELECT FOSDisplay FROM whed_lex_fos WHERE Valide=1 AND FOSLevel IN (1,2) ORDER BY FOSCode",
            "FOSDisplay",
        ),
        "languages": _col(
            "SELECT Language FROM whed_lex_language ORDER BY Language",
            "Language",
        ),
        "cred_cat": _pairs(
            "SELECT CredCatCode, CredCat FROM whed_lex_credcat",
            "CredCatCode", "CredCat",
        ),
        "cred_level": _pairs(
            "SELECT CredLevelCode, CredLevel FROM whed_lex_credlevel ORDER BY CredLevelID",
            "CredLevelCode", "CredLevel",
        ),
        "gender": [
            {"code": "M", "label": "Male"},
            {"code": "F", "label": "Female"},
            {"code": "X", "label": "Non-binary / Other"},
        ],
    }
    conn.close()
    return data


def get_national_inst_types(country_code: str) -> list[str]:
    """Return country-specific institution types from whed_tcsinsttype."""
    conn = _get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT sInstType FROM whed_tcsinsttype "
        "WHERE StateID IN (SELECT StateID FROM whed_state WHERE CountryCode=%s) "
        "ORDER BY sInstTypeSort",
        (country_code,),
    )
    result = [row["sInstType"] for row in c.fetchall() if row["sInstType"]]
    conn.close()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Few-shot reference example
# ─────────────────────────────────────────────────────────────────────────────

def get_reference_example(country_code: str) -> Optional[dict]:
    """
    Fetch one complete institution record from the same country,
    formatted to match the SchoolProfile JSON structure.
    Picks a UV (university-level) institution with the most data.
    """
    conn = _get_connection()
    c = conn.cursor()

    c.execute(
        "SELECT OrgID, OrgName, InstNameEnglish, InstAcronym, "
        "       InstClassCode, InstFundingTypeCode, iCreated, iPresentStatusYear, "
        "       City, Street, Province, PostCode, Tel, Email, WWW, "
        "       iHistory, iAcademicYear, iAdmissionRequirements, iAccreditingAgency, "
        "       iStudentBody, iLearning, iFeesN, iFeesI "
        "FROM whed_org "
        "WHERE CountryCode=%s AND InstClassCode='UV' AND OrgName IS NOT NULL "
        "ORDER BY CHAR_LENGTH(COALESCE(iHistory,'')) DESC "
        "LIMIT 1",
        (country_code,),
    )
    org = c.fetchone()
    if not org:
        conn.close()
        return None

    org_id = org["OrgID"]

    # Contacts
    c.execute(
        "SELECT FirstName, Surname, JobTitle, JobFunctionCode, "
        "       ContactEMail, Sex, YearsOfOffice "
        "FROM whed_contact WHERE OrgID=%s LIMIT 5",
        (org_id,),
    )
    contacts_raw = c.fetchall()

    # Divisions (with FOS)
    c.execute(
        "SELECT d.iDivisionID, d.iDivision, d.iDivisionTypeCode, d.iMoreDetails "
        "FROM whed_division d WHERE d.OrgID=%s LIMIT 10",
        (org_id,),
    )
    divisions_raw = c.fetchall()
    for div in divisions_raw:
        c.execute(
            "SELECT f.FOSDisplay FROM whed_tlidivisionfoslink l "
            "JOIN whed_lex_fos f ON l.FOSCode=f.FOSCode "
            "WHERE l.iDivisionID=%s AND f.Valide=1 LIMIT 8",
            (div["iDivisionID"],),
        )
        div["fos"] = [r["FOSDisplay"] for r in c.fetchall()]

    # Degrees
    c.execute(
        "SELECT d.iDegree, cr.Cred, cr.CredLevelCode "
        "FROM whed_degree d "
        "JOIN whed_cred cr ON d.CredID=cr.CredID "
        "WHERE d.OrgID=%s LIMIT 10",
        (org_id,),
    )
    degrees_raw = c.fetchall()

    # Languages
    c.execute(
        "SELECT l.Language FROM whed_lex_language l "
        "WHERE l.LanguageCode IN ("
        "  SELECT ol.LanguageCode FROM whed_tlsstatelanguagelink ol "
        "  WHERE ol.StateID=(SELECT StateID FROM whed_org WHERE OrgID=%s)"
        ") LIMIT 5",
        (org_id,),
    )
    languages = [r["Language"] for r in c.fetchall()]

    # National institution type
    c.execute(
        "SELECT t.sInstType FROM whed_tcsinsttype t "
        "JOIN whed_org o ON t.StateID=o.StateID AND t.sInstTypeID=o.sInstTypeID "
        "WHERE o.OrgID=%s",
        (org_id,),
    )
    nat_type_row = c.fetchone()
    nat_type = nat_type_row["sInstType"] if nat_type_row else None

    conn.close()

    # Job function code → label
    jf_map = {"1H": "Head of Institution", "2A": "Senior Admin Officer", "3R": "International Relations Officer"}
    # Division type code → label
    dt_lookup = {p["code"]: p["label"] for p in get_picklists()["division_type"]}

    example = {
        "org_basics": {
            "name_native": org["OrgName"],
            "name_english": org["InstNameEnglish"] or org["OrgName"],
            "is_branch": False,
            "year_founded": org["iCreated"],
            "institution_type_international": org["InstClassCode"],
            "institution_type_national": nat_type,
            "funding_type": org["InstFundingTypeCode"],
            "acronym": org["InstAcronym"],
        },
        "contact": {
            "city": org["City"],
            "street": org["Street"],
            "province": org["Province"],
            "post_code": org["PostCode"],
            "website": org["WWW"],
            "email": org["Email"],
            "phone": org["Tel"],
        },
        "academic": {
            "languages_of_instruction": languages,
            "accrediting_body": org["iAccreditingAgency"],
            "history": (org["iHistory"] or "")[:300] or None,
            "student_body": org["iStudentBody"],
            "learning_modalities": org["iLearning"],
        },
        "tuition": {
            "national_students": org["iFeesN"],
            "international_students": org["iFeesI"],
        },
        "key_contacts": [
            {
                "first_name": ct["FirstName"],
                "surname": ct["Surname"],
                "job_title": ct["JobTitle"],
                "job_function": jf_map.get(ct["JobFunctionCode"], ct["JobFunctionCode"]),
                "email": ct["ContactEMail"],
                "gender": ct["Sex"],
                "years_of_office": ct["YearsOfOffice"],
            }
            for ct in contacts_raw
        ],
        "divisions": [
            {
                "name": dv["iDivision"],
                "division_type": dt_lookup.get(dv["iDivisionTypeCode"], dv["iDivisionTypeCode"]),
                "fields_of_study": dv["fos"],
            }
            for dv in divisions_raw
        ],
        "degree_programs": [
            {
                "name": dg["iDegree"],
                "level": dg["Cred"],
                "cred_level_code": dg["CredLevelCode"],
            }
            for dg in degrees_raw
        ],
    }
    return example


# ─────────────────────────────────────────────────────────────────────────────
# Build the full DB context block for the LLM prompt
# ─────────────────────────────────────────────────────────────────────────────

def build_db_context(domain: str) -> str:
    """
    Build a text block with picklists + reference example to inject into
    the extraction prompt. Returns empty string if DB is unavailable.
    """
    if not is_db_available():
        logger.info("WHED DB not available — skipping DB grounding")
        return ""

    country_code = detect_country_code(domain)
    picklists = get_picklists()

    lines = [
        "=" * 60,
        "REFERENCE DATA FROM WHED DATABASE (use these to guide your output)",
        "=" * 60,
        "",
        "ALLOWED VALUES — use exact values from these lists:",
        "",
    ]

    # Institution class
    ic_str = ", ".join(f"{p['code']} ({p['label']})" for p in picklists["inst_class"])
    lines.append(f"  institution_type_international: {ic_str}")

    # Funding type
    ft_str = ", ".join(f"{p['code']} ({p['label']})" for p in picklists["funding_type"])
    lines.append(f"  funding_type: {ft_str}")

    # National institution types (country-specific)
    if country_code:
        nat_types = get_national_inst_types(country_code)
        if nat_types:
            lines.append(f"  institution_type_national ({country_code}): {', '.join(nat_types)}")

    # Division types
    dt_str = ", ".join(f"{p['label']}" for p in picklists["division_type"])
    lines.append(f"  division_type: {dt_str}")

    # Job functions
    jf_str = ", ".join(f"{p['label']} (code: {p['code']})" for p in picklists["job_function"])
    lines.append(f"  job_function: {jf_str}")

    # Gender
    g_str = ", ".join(f"{p['code']} ({p['label']})" for p in picklists["gender"])
    lines.append(f"  gender: {g_str}")

    # Fields of study (top-level + level-2, truncated for prompt size)
    fos_sample = picklists["fos"][:80]
    lines.append(f"  fields_of_study ({len(picklists['fos'])} options, showing first {len(fos_sample)}):")
    lines.append(f"    {', '.join(fos_sample)}")

    # Languages
    lines.append(f"  languages_of_instruction: {', '.join(picklists['languages'][:40])}")

    # Credential categories
    cc_str = ", ".join(f"{p['label']} ({p['code']})" for p in picklists["cred_cat"])
    lines.append(f"  credential_category: {cc_str}")

    # Reference example
    if country_code:
        example = get_reference_example(country_code)
        if example:
            lines.extend([
                "",
                "-" * 60,
                f"REFERENCE EXAMPLE (existing {country_code} institution from WHED database):",
                "Follow this format, field names, and value conventions exactly.",
                "-" * 60,
                json.dumps(example, indent=2, ensure_ascii=False, default=str),
            ])

    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Ground truth export — full institution record from WHED DB
# ─────────────────────────────────────────────────────────────────────────────

def export_ground_truth(domain: str) -> Optional[dict]:
    """
    Look up an institution by its website domain in whed_org.WWW,
    then export its full record in SchoolProfile-compatible JSON.
    Returns None if not found.
    """
    if not is_db_available():
        return None

    conn = _get_connection()
    c = conn.cursor()

    # Match by domain in WWW field
    bare = domain.lower().replace("www.", "")
    c.execute(
        "SELECT OrgID FROM whed_org WHERE LOWER(WWW) LIKE %s LIMIT 1",
        (f"%{bare}%",),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return None

    org_id = row["OrgID"]
    return _export_org(conn, org_id)


def export_ground_truth_by_id(org_id: int) -> Optional[dict]:
    """Export a full institution record by OrgID."""
    if not is_db_available():
        return None
    conn = _get_connection()
    return _export_org(conn, org_id)


def _export_org(conn, org_id: int) -> Optional[dict]:
    """Internal: build a full SchoolProfile-shaped dict from whed_org + related tables."""
    c = conn.cursor()

    # Main org record
    c.execute(
        "SELECT o.*, s.Country, s.State, "
        "       t.sInstType AS national_inst_type "
        "FROM whed_org o "
        "LEFT JOIN whed_state s ON o.StateID = s.StateID "
        "LEFT JOIN whed_tcsinsttype t ON o.StateID = t.StateID AND o.sInstTypeID = t.sInstTypeID "
        "WHERE o.OrgID = %s",
        (org_id,),
    )
    org = c.fetchone()
    if not org:
        conn.close()
        return None

    # Contacts
    c.execute("SELECT * FROM whed_contact WHERE OrgID = %s", (org_id,))
    contacts = c.fetchall()

    # Divisions + FOS
    c.execute("SELECT * FROM whed_division WHERE OrgID = %s", (org_id,))
    divisions = c.fetchall()
    for div in divisions:
        c.execute(
            "SELECT f.FOSDisplay FROM whed_tlidivisionfoslink l "
            "JOIN whed_lex_fos f ON l.FOSCode = f.FOSCode "
            "WHERE l.iDivisionID = %s AND f.Valide = 1",
            (div["iDivisionID"],),
        )
        div["_fos"] = [r["FOSDisplay"] for r in c.fetchall()]

    # Degrees + credential info
    c.execute(
        "SELECT d.iDegreeID, d.iDegree, cr.Cred, cr.CredLevelCode, cr.CredCatCode1 "
        "FROM whed_degree d "
        "LEFT JOIN whed_cred cr ON d.CredID = cr.CredID "
        "WHERE d.OrgID = %s",
        (org_id,),
    )
    degrees = c.fetchall()
    for deg in degrees:
        c.execute(
            "SELECT f.FOSDisplay FROM whed_tlidegreefoslink l "
            "JOIN whed_lex_fos f ON l.FOSCode = f.FOSCode "
            "WHERE l.iDegreeID = %s AND f.Valide = 1",
            (deg["iDegreeID"],),
        )
        deg["_fos"] = [r["FOSDisplay"] for r in c.fetchall()]

    # Languages of instruction
    c.execute(
        "SELECT l.Language FROM whed_lex_language l "
        "WHERE l.LanguageCode IN ("
        "  SELECT sl.LanguageCode FROM whed_tlsstatelanguagelink sl "
        "  WHERE sl.StateID = %s"
        ")",
        (org.get("StateID"),),
    )
    languages = [r["Language"] for r in c.fetchall()]

    # Division type lookup
    dt_lookup = {p["code"]: p["label"] for p in get_picklists()["division_type"]}
    jf_map = {"1H": "Head of Institution", "2A": "Senior Admin Officer", "3R": "International Relations Officer"}
    gender_map = {"M": "Male", "F": "Female", "X": "Non-binary / Other"}

    profile = {
        "domain": (org.get("WWW") or "").replace("https://", "").replace("http://", "").rstrip("/"),
        "source_url": org.get("WWW") or "",
        "extracted_at": "WHED_DB_GROUND_TRUTH",
        "extraction_model": "WHED_DB",
        "org_basics": {
            "name_native": org.get("OrgName"),
            "name_english": org.get("InstNameEnglish") or org.get("OrgName"),
            "is_branch": bool(org.get("iParentOrgID")),
            "year_founded": org.get("iCreated"),
            "institution_type_international": org.get("InstClassCode"),
            "institution_type_national": org.get("national_inst_type"),
            "funding_type": org.get("InstFundingTypeCode"),
            "year_acquired_status": org.get("iPresentStatusYear"),
            "other_campuses": org.get("iOtherSites"),
            "acronym": org.get("InstAcronym"),
        },
        "contact": {
            "city": org.get("City"),
            "street": org.get("Street"),
            "province": org.get("Province"),
            "post_code": org.get("PostCode"),
            "website": org.get("WWW"),
            "email": org.get("Email"),
            "phone": org.get("Tel"),
        },
        "academic": {
            "languages_of_instruction": languages,
            "accrediting_body": org.get("iAccreditingAgency"),
            "history": org.get("iHistory"),
            "academic_year": org.get("iAcademicYear"),
            "admission_requirements": org.get("iAdmissionRequirements"),
            "student_body": org.get("iStudentBody"),
            "learning_modalities": org.get("iLearning"),
        },
        "tuition": {
            "national_students": org.get("iFeesN"),
            "international_students": org.get("iFeesI"),
        },
        "key_contacts": [
            {
                "first_name": ct.get("FirstName"),
                "surname": ct.get("Surname"),
                "job_title": ct.get("JobTitle"),
                "job_function": jf_map.get(ct.get("JobFunctionCode"), ct.get("JobFunctionCode")),
                "email": ct.get("ContactEMail"),
                "gender": gender_map.get(ct.get("Sex"), ct.get("Sex")),
                "years_of_office": ct.get("YearsOfOffice"),
                "phone": ct.get("ContactTel"),
                "verification_status": "verified",
            }
            for ct in contacts
        ],
        "divisions": [
            {
                "name": dv.get("iDivision"),
                "division_type": dt_lookup.get(dv.get("iDivisionTypeCode"), dv.get("iDivisionTypeCode")),
                "fields_of_study": dv["_fos"],
                "details": dv.get("iMoreDetails"),
            }
            for dv in divisions
        ],
        "degree_programs": [
            {
                "name": dg.get("iDegree"),
                "level": dg.get("Cred"),
                "department": None,
                "duration": None,
                "language_of_instruction": None,
                "tuition_fee": None,
                "entry_requirements": None,
                "_fos": dg["_fos"],
                "_cred_level_code": dg.get("CredLevelCode"),
                "_cred_cat": dg.get("CredCatCode1"),
            }
            for dg in degrees
        ],
        "other": {
            "student_numbers": None,
            "institutional_publications": None,
        },
        "extraction_notes": None,
    }

    conn.close()
    return profile


# ─────────────────────────────────────────────────────────────────────────────
# Structured staging tables — reviewed profiles ready for import into WHED
# ─────────────────────────────────────────────────────────────────────────────

_STAGING_DDL = [
    """\
CREATE TABLE IF NOT EXISTS staging_org (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    domain                VARCHAR(255) NOT NULL UNIQUE,
    source_url            VARCHAR(500),
    extracted_at          VARCHAR(50),
    -- org_basics (mirrors whed_org)
    OrgName               VARCHAR(160),
    InstNameEnglish       VARCHAR(160),
    is_branch             TINYINT(1) DEFAULT 0,
    iCreated              VARCHAR(50),
    InstClassCode         VARCHAR(2),
    inst_type_national    VARCHAR(255),
    InstFundingTypeCode   VARCHAR(2),
    -- contact (mirrors whed_org address block)
    City                  VARCHAR(60),
    Street                TEXT,
    Province              VARCHAR(60),
    PostCode              VARCHAR(40),
    WWW                   TEXT,
    EMail                 VARCHAR(100),
    Tel                   VARCHAR(60),
    -- meta
    extraction_notes      TEXT,
    review_action         ENUM('pending','accept','modify','reject') NOT NULL DEFAULT 'pending',
    notes                 TEXT,
    reviewed_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
    """\
CREATE TABLE IF NOT EXISTS staging_contacts (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    staging_org_id    INT NOT NULL,
    position_order    INT DEFAULT 0,
    Surname           VARCHAR(60),
    FirstName         VARCHAR(60),
    JobTitle          VARCHAR(100),
    job_function      VARCHAR(100),
    ContactEMail      VARCHAR(100),
    Sex               VARCHAR(1),
    FOREIGN KEY (staging_org_id) REFERENCES staging_org(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
    """\
CREATE TABLE IF NOT EXISTS staging_divisions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    staging_org_id    INT NOT NULL,
    iDivision         VARCHAR(255),
    division_type     VARCHAR(100),
    fields_of_study   TEXT,
    FOREIGN KEY (staging_org_id) REFERENCES staging_org(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
    """\
CREATE TABLE IF NOT EXISTS staging_degrees (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    staging_org_id    INT NOT NULL,
    iDegree           VARCHAR(255),
    degree_level      VARCHAR(100),
    FOREIGN KEY (staging_org_id) REFERENCES staging_org(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
    """\
CREATE TABLE IF NOT EXISTS staging_review_log (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    domain            VARCHAR(255) NOT NULL,
    review_action     ENUM('pending','accept','modify','reject') NOT NULL,
    notes             TEXT,
    reviewed_at       DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
    """\
CREATE TABLE IF NOT EXISTS staging_comparison (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    staging_org_id  INT NOT NULL,
    whed_org_id     MEDIUMINT UNSIGNED,
    field_name      VARCHAR(80) NOT NULL,
    staged_value    TEXT,
    whed_value      TEXT,
    similarity      FLOAT,
    match_method    ENUM('cosine','exact') DEFAULT 'cosine',
    compared_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staging_org_id) REFERENCES staging_org(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
]


def ensure_staging_tables() -> bool:
    """Create all staging tables if they do not exist. Returns True on success."""
    try:
        conn = _get_connection()
        with conn.cursor() as c:
            for ddl in _STAGING_DDL:
                c.execute(ddl)
        conn.commit()
        conn.close()
        logger.info("All staging tables ready")
        return True
    except Exception as exc:
        logger.warning("Could not create staging tables: %s", exc)
        return False


def upsert_staging(
    domain: str,
    review_action: str,
    profile: dict,
    notes: Optional[str] = None,
) -> bool:
    """
    Decompose a SchoolProfile dict into structured staging rows.
    Upserts staging_org, replaces child rows, and appends a review log entry.
    """
    try:
        conn = _get_connection()
        c = conn.cursor()

        ob = profile.get("org_basics") or {}
        ct = profile.get("contact") or {}

        c.execute(
            "INSERT INTO staging_org "
            "(domain, source_url, extracted_at, "
            " OrgName, InstNameEnglish, is_branch, iCreated, "
            " InstClassCode, inst_type_national, InstFundingTypeCode, "
            " City, Street, Province, PostCode, WWW, EMail, Tel, "
            " extraction_notes, review_action, notes) "
            "VALUES (%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,%s,%s,%s, %s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " source_url=VALUES(source_url), extracted_at=VALUES(extracted_at), "
            " OrgName=VALUES(OrgName), InstNameEnglish=VALUES(InstNameEnglish), "
            " is_branch=VALUES(is_branch), iCreated=VALUES(iCreated), "
            " InstClassCode=VALUES(InstClassCode), inst_type_national=VALUES(inst_type_national), "
            " InstFundingTypeCode=VALUES(InstFundingTypeCode), "
            " City=VALUES(City), Street=VALUES(Street), Province=VALUES(Province), "
            " PostCode=VALUES(PostCode), WWW=VALUES(WWW), EMail=VALUES(EMail), Tel=VALUES(Tel), "
            " extraction_notes=VALUES(extraction_notes), "
            " review_action=VALUES(review_action), notes=VALUES(notes), "
            " reviewed_at=NOW()",
            (
                domain,
                profile.get("source_url"),
                profile.get("extracted_at"),
                ob.get("name_native"),
                ob.get("name_english"),
                1 if ob.get("is_branch") else 0,
                str(ob.get("year_founded", "")) or None,
                ob.get("institution_type_international"),
                ob.get("institution_type_national"),
                ob.get("funding_type"),
                ct.get("city"),
                ct.get("street"),
                ct.get("province"),
                ct.get("post_code"),
                ct.get("website") or profile.get("source_url"),
                ct.get("email"),
                ct.get("phone"),
                profile.get("extraction_notes"),
                review_action,
                notes,
            ),
        )

        c.execute(
            "SELECT id FROM staging_org WHERE domain=%s", (domain,)
        )
        org_row = c.fetchone()
        org_id = org_row["id"]

        # Replace child rows (delete + re-insert)
        for child_table in ("staging_contacts", "staging_divisions", "staging_degrees"):
            c.execute(f"DELETE FROM {child_table} WHERE staging_org_id=%s", (org_id,))

        # Contacts
        for idx, kc in enumerate(profile.get("key_contacts") or []):
            c.execute(
                "INSERT INTO staging_contacts "
                "(staging_org_id, position_order, Surname, FirstName, "
                " JobTitle, job_function, ContactEMail, Sex) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    org_id, idx,
                    kc.get("surname"),
                    kc.get("first_name"),
                    kc.get("job_title"),
                    kc.get("job_function"),
                    kc.get("email"),
                    kc.get("gender"),
                ),
            )

        # Divisions
        for dv in profile.get("divisions") or []:
            fos = dv.get("fields_of_study") or []
            fos_str = ", ".join(fos) if isinstance(fos, list) else str(fos)
            c.execute(
                "INSERT INTO staging_divisions "
                "(staging_org_id, iDivision, division_type, fields_of_study) "
                "VALUES (%s,%s,%s,%s)",
                (org_id, dv.get("name"), dv.get("division_type"), fos_str),
            )

        # Degrees
        for dg in profile.get("degree_programs") or []:
            c.execute(
                "INSERT INTO staging_degrees "
                "(staging_org_id, iDegree, degree_level) "
                "VALUES (%s,%s,%s)",
                (org_id, dg.get("name"), dg.get("level")),
            )

        # Audit log (always append)
        c.execute(
            "INSERT INTO staging_review_log (domain, review_action, notes) "
            "VALUES (%s,%s,%s)",
            (domain, review_action, notes),
        )

        conn.commit()
        conn.close()
        logger.info("Staged %s (%s) — org + %d contacts + %d divisions + %d degrees",
                     domain, review_action,
                     len(profile.get("key_contacts") or []),
                     len(profile.get("divisions") or []),
                     len(profile.get("degree_programs") or []))
        return True
    except Exception as exc:
        logger.warning("DB staging failed for %s: %s", domain, exc)
        return False
