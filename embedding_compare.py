"""
embedding_compare.py — Per-field cosine similarity between staged and WHED data
================================================================================
After a profile is staged, this module:
  1. Finds the matching WHED record (by domain in whed_org.WWW)
  2. For each comparable field, generates embeddings on-the-fly
  3. Computes cosine similarity
  4. Stores results in staging_comparison table

Uses sentence-transformers (all-MiniLM-L6-v2) for embedding generation.
"""

import logging
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from db_reference import _get_connection, is_db_available

logger = logging.getLogger(__name__)

_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded")
    return _model


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# Fields to compare: (field_name, staging_col_or_path, whed_col_or_path)
# "exact" fields use string equality; "cosine" fields use embedding similarity
_ORG_FIELDS = [
    ("OrgName",               "cosine"),
    ("InstNameEnglish",       "cosine"),
    ("iCreated",              "exact"),
    ("InstClassCode",         "exact"),
    ("inst_type_national",    "cosine"),
    ("InstFundingTypeCode",   "exact"),
    ("City",                  "cosine"),
    ("Street",                "cosine"),
    ("Province",              "cosine"),
    ("PostCode",              "exact"),
    ("EMail",                 "exact"),
    ("Tel",                   "exact"),
]

# Mapping: staging_org column → whed_org column (when names differ)
_STAGING_TO_WHED = {
    "inst_type_national": "national_inst_type",
}


def _find_whed_org(conn, domain: str) -> Optional[dict]:
    """Look up the WHED record matching this domain."""
    bare = domain.lower().replace("www.", "")
    c = conn.cursor()
    c.execute(
        "SELECT o.OrgID, o.OrgName, o.InstNameEnglish, o.iCreated, "
        "  o.InstClassCode, o.InstFundingTypeCode, "
        "  o.City, o.Street, o.Province, o.PostCode, o.EMail, o.Tel, "
        "  t.sInstType AS national_inst_type "
        "FROM whed_org o "
        "LEFT JOIN whed_tcsinsttype t ON o.StateID = t.StateID AND o.sInstTypeID = t.sInstTypeID "
        "WHERE LOWER(o.WWW) LIKE %s LIMIT 1",
        (f"%{bare}%",),
    )
    return c.fetchone()


def _find_staging_org(conn, domain: str) -> Optional[dict]:
    """Fetch the staged record for this domain."""
    c = conn.cursor()
    c.execute("SELECT * FROM staging_org WHERE domain = %s", (domain,))
    return c.fetchone()


def compare_staged_vs_whed(domain: str) -> dict:
    """
    Per-field comparison between staging_org and whed_org.
    Returns summary dict with field scores.
    """
    if not is_db_available():
        return {"success": False, "error": "DB not available"}

    conn = _get_connection()

    staged = _find_staging_org(conn, domain)
    if not staged:
        conn.close()
        return {"success": False, "error": f"No staged record for {domain}"}

    whed = _find_whed_org(conn, domain)
    if not whed:
        conn.close()
        return {
            "success": True,
            "domain": domain,
            "whed_match": False,
            "note": "No matching WHED record found — this may be a new institution",
            "fields": [],
        }

    staging_org_id = staged["id"]
    whed_org_id = whed["OrgID"]

    # Clear previous comparison for this staging record
    c = conn.cursor()
    c.execute("DELETE FROM staging_comparison WHERE staging_org_id = %s", (staging_org_id,))

    model = _get_model()
    results = []

    # Collect texts for batch encoding
    cosine_pairs = []
    exact_pairs = []

    for field_name, method in _ORG_FIELDS:
        staged_val = staged.get(field_name)
        whed_col = _STAGING_TO_WHED.get(field_name, field_name)
        whed_val = whed.get(whed_col)

        s_str = str(staged_val).strip() if staged_val else ""
        w_str = str(whed_val).strip() if whed_val else ""

        if method == "exact":
            exact_pairs.append((field_name, s_str, w_str))
        else:
            cosine_pairs.append((field_name, s_str, w_str))

    # Batch encode all cosine texts at once
    all_texts = []
    for _, s_str, w_str in cosine_pairs:
        all_texts.append(s_str if s_str else "(empty)")
        all_texts.append(w_str if w_str else "(empty)")

    embeddings = model.encode(all_texts, convert_to_numpy=True) if all_texts else np.array([])

    # Process cosine pairs
    for i, (field_name, s_str, w_str) in enumerate(cosine_pairs):
        if not s_str and not w_str:
            sim = 1.0
        elif not s_str or not w_str:
            sim = 0.0
        else:
            emb_s = embeddings[i * 2]
            emb_w = embeddings[i * 2 + 1]
            sim = cosine_similarity(emb_s, emb_w)

        results.append({
            "field": field_name,
            "staged": s_str,
            "whed": w_str,
            "similarity": round(sim, 4),
            "method": "cosine",
        })
        c.execute(
            "INSERT INTO staging_comparison "
            "(staging_org_id, whed_org_id, field_name, staged_value, whed_value, similarity, match_method) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'cosine')",
            (staging_org_id, whed_org_id, field_name, s_str or None, w_str or None, round(sim, 4)),
        )

    # Process exact pairs
    for field_name, s_str, w_str in exact_pairs:
        if not s_str and not w_str:
            sim = 1.0
        elif s_str.lower() == w_str.lower():
            sim = 1.0
        else:
            sim = 0.0

        results.append({
            "field": field_name,
            "staged": s_str,
            "whed": w_str,
            "similarity": round(sim, 4),
            "method": "exact",
        })
        c.execute(
            "INSERT INTO staging_comparison "
            "(staging_org_id, whed_org_id, field_name, staged_value, whed_value, similarity, match_method) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'exact')",
            (staging_org_id, whed_org_id, field_name, s_str or None, w_str or None, round(sim, 4)),
        )

    conn.commit()

    # Contacts comparison
    contact_results = _compare_contacts(conn, staging_org_id, whed_org_id, model)
    results.extend(contact_results)

    # Divisions comparison
    division_results = _compare_divisions(conn, staging_org_id, whed_org_id, model)
    results.extend(division_results)

    conn.close()

    similarities = [r["similarity"] for r in results]
    avg_sim = round(sum(similarities) / len(similarities), 4) if similarities else 0.0

    return {
        "success": True,
        "domain": domain,
        "whed_match": True,
        "whed_org_id": whed_org_id,
        "avg_similarity": avg_sim,
        "field_count": len(results),
        "fields": results,
    }


def _compare_contacts(conn, staging_org_id: int, whed_org_id: int, model) -> list[dict]:
    """Compare staged contacts vs WHED contacts by best-match pairing on name."""
    c = conn.cursor()
    c.execute(
        "SELECT FirstName, Surname, JobTitle, job_function FROM staging_contacts "
        "WHERE staging_org_id = %s ORDER BY position_order",
        (staging_org_id,),
    )
    staged_contacts = c.fetchall()

    c.execute(
        "SELECT FirstName, Surname, JobTitle, JobFunctionCode FROM whed_contact "
        "WHERE OrgID = %s",
        (whed_org_id,),
    )
    whed_contacts = c.fetchall()

    if not staged_contacts or not whed_contacts:
        return []

    results = []
    staged_names = [f"{ct['FirstName'] or ''} {ct['Surname'] or ''}".strip() for ct in staged_contacts]
    whed_names = [f"{ct['FirstName'] or ''} {ct['Surname'] or ''}".strip() for ct in whed_contacts]

    all_names = staged_names + whed_names
    if all_names:
        embs = model.encode(all_names, convert_to_numpy=True)
        s_embs = embs[:len(staged_names)]
        w_embs = embs[len(staged_names):]

        for i, s_name in enumerate(staged_names):
            best_sim = 0.0
            best_j = 0
            for j in range(len(whed_names)):
                sim = cosine_similarity(s_embs[i], w_embs[j])
                if sim > best_sim:
                    best_sim = sim
                    best_j = j

            results.append({
                "field": f"contact[{i}].name",
                "staged": s_name,
                "whed": whed_names[best_j] if whed_names else "",
                "similarity": round(best_sim, 4),
                "method": "cosine",
            })
            c.execute(
                "INSERT INTO staging_comparison "
                "(staging_org_id, whed_org_id, field_name, staged_value, whed_value, similarity, match_method) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'cosine')",
                (staging_org_id, whed_org_id, f"contact[{i}].name",
                 s_name, whed_names[best_j] if whed_names else None, round(best_sim, 4)),
            )

    conn.commit()
    return results


def _compare_divisions(conn, staging_org_id: int, whed_org_id: int, model) -> list[dict]:
    """Compare staged divisions vs WHED divisions by best-match pairing on name."""
    c = conn.cursor()
    c.execute(
        "SELECT iDivision, division_type FROM staging_divisions WHERE staging_org_id = %s",
        (staging_org_id,),
    )
    staged_divs = c.fetchall()

    c.execute(
        "SELECT iDivision, iDivisionTypeCode FROM whed_division WHERE OrgID = %s",
        (whed_org_id,),
    )
    whed_divs = c.fetchall()

    if not staged_divs or not whed_divs:
        return []

    results = []
    staged_names = [d["iDivision"] or "" for d in staged_divs]
    whed_names = [d["iDivision"] or "" for d in whed_divs]

    all_names = staged_names + whed_names
    if all_names:
        embs = model.encode(all_names, convert_to_numpy=True)
        s_embs = embs[:len(staged_names)]
        w_embs = embs[len(staged_names):]

        for i, s_name in enumerate(staged_names):
            best_sim = 0.0
            best_j = 0
            for j in range(len(whed_names)):
                sim = cosine_similarity(s_embs[i], w_embs[j])
                if sim > best_sim:
                    best_sim = sim
                    best_j = j

            results.append({
                "field": f"division[{i}].name",
                "staged": s_name,
                "whed": whed_names[best_j] if whed_names else "",
                "similarity": round(best_sim, 4),
                "method": "cosine",
            })
            c.execute(
                "INSERT INTO staging_comparison "
                "(staging_org_id, whed_org_id, field_name, staged_value, whed_value, similarity, match_method) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'cosine')",
                (staging_org_id, whed_org_id, f"division[{i}].name",
                 s_name, whed_names[best_j] if whed_names else None, round(best_sim, 4)),
            )

    conn.commit()
    return results
